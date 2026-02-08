from fastapi.security import OAuth2PasswordBearer  
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional
from dotenv import load_dotenv
import os
import base64
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form, Body, Request
from starlette.requests import Request

# Load env vars
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
JWT_EXPIRE_MINUTES = 14400

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ---------- FastAPI app ----------
app = FastAPI()

# CORS (agar HTML ko alag port se serve kar rahe ho)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Mongo Connection ----------
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]
user_collection = db["user"]   


# ---------- Models ----------
class UserCreate(BaseModel):
    employee_code: str
    password: str


class UserLogin(BaseModel):
    employee_code: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    employee_code: Optional[str] = None


# ---------- Utility functions ----------
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


async def get_user_by_employee_code(employee_code: str):
    return await user_collection.find_one({"employee_code": employee_code})


# ---------- JWT dependency ----------
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")  # logical name


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        employee_code: str = payload.get("sub")
        if employee_code is None:
            raise credentials_exception
        token_data = TokenData(employee_code=employee_code)
    except JWTError:
        raise credentials_exception

    user = await get_user_by_employee_code(token_data.employee_code)
    if user is None:
        raise credentials_exception
    return user


async def is_valid_employee(employee_code: str) -> bool:
    emp = await db["Employee_details"].find_one({"Employee_ID": employee_code})
    return emp is not None

# ---------- Auth endpoints ----------

@app.post("/api/register")
async def register(user: UserCreate):
    print("📌 Incoming register data:", user.employee_code)

    # Check if exists
    existing = await user_collection.find_one({"employee_code": user.employee_code})
    print("📌 Existing user:", existing)

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Employee already registered"
        )

    hashed_password = get_password_hash(user.password)
    print("📌 Password hashed")

    doc = {
        "employee_code": user.employee_code,
        "password_hash": hashed_password,
        "created_at": datetime.utcnow()
    }

    result = await user_collection.insert_one(doc)
    print("📌 Insert result:", result.inserted_id)

    return {"message": "Registered successfully"}

@app.post("/api/login", response_model=Token)
async def login(user: UserLogin):
    db_user = await get_user_by_employee_code(user.employee_code)
    if not db_user:
        raise HTTPException(status_code=401, detail="Incorrect employee code or password")

    if not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect employee code or password")

    access_token = create_access_token(
        data={"sub": user.employee_code}
    )

    return {"access_token": access_token, "token_type": "bearer"}


# ---------- Protected example route ----------
@app.get("/api/me")
async def read_current_user(current_user=Depends(get_current_user)):
    # yaha future me Employee_details se jo marzi data fetch kar sakte ho
    return {
        "employee_code": current_user["employee_code"],
        "created_at": current_user.get("created_at"),
    }


# Employee Details Fetch from Backend
@app.get("/api/employee/{employee_code}")
async def get_employee_details(employee_code: str, current_user=Depends(get_current_user)):

    emp = await db["Employee_details"].find_one({"EmpID": employee_code})

    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {
        "employee_id": emp.get("EmpID"),
        "employee_name": emp.get("Emp Name"),
        "designation": emp.get("Designation Name"),
        "gender": emp.get("Gender"),
        "partner": emp.get("Partner"),
        "reporting_manager_code": emp.get("ReportingEmpCode"),
        "reporting_manager_name": emp.get("ReportingEmpName"),
        "ope_limit": emp.get("OPE Limit")
    }


# ---------- OPE Data Submission ----------
@app.post("/api/ope/submit")
async def submit_ope_entry(
    date: str = Form(...),
    client: str = Form(...),
    project_id: str = Form(...),
    project_name: str = Form(...),
    project_type: str = Form(...),
    location_from: str = Form(...),
    location_to: str = Form(...),
    travel_mode: str = Form(...),
    amount: float = Form(...),
    remarks: str = Form(...),
    month_range: str = Form(...),
    ticket_pdf: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user)
):
    try:
        employee_code = current_user["employee_code"]
        
        print(f"📌 Submitting OPE entry for: {employee_code}")
        print(f"📌 Month range received: {month_range}")
        print(f"📌 Project type: {project_type}")
        print(f"📌 Date: {date}")
        print(f"📌 Amount: {amount}")
        
        # Validate amount
        if amount <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Amount must be greater than 0, received: {amount}"
            )
        
        # Format month_range from "sep-oct-2025" to "Sep 2025 - Oct 2025"
        def format_month_range(month_str):
            """
            Convert "sep-oct-2025" to "Sep 2025 - Oct 2025"
            Convert "jan-2025" to "Jan 2025"
            """
            try:
                parts = month_str.lower().split('-')
                
                # Month mapping
                month_map = {
                    'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
                    'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
                    'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
                }
                
                if len(parts) == 3:  # e.g., "sep-oct-2025"
                    month1 = month_map.get(parts[0], parts[0].capitalize())
                    month2 = month_map.get(parts[1], parts[1].capitalize())
                    year = parts[2]
                    return f"{month1} {year} - {month2} {year}"
                elif len(parts) == 2:  # e.g., "jan-2025"
                    month = month_map.get(parts[0], parts[0].capitalize())
                    year = parts[1]
                    return f"{month} {year}"
                else:
                    return month_str  # Return as-is if format unexpected
            except Exception as e:
                print(f"⚠️ Error formatting month range: {e}")
                return month_str
        
        formatted_month_range = format_month_range(month_range)
        print(f"✅ Formatted month range: {formatted_month_range}")
        
        # Get employee details
        emp = await db["Employee_details"].find_one({"EmpID": employee_code})
        if not emp:
            print(f"❌ Employee not found: {employee_code}")
            raise HTTPException(
                status_code=404,
                detail=f"Employee details not found for code: {employee_code}"
            )
        
        print(f"✅ Employee found: {emp.get('Emp Name')}")
        
        # ✅ CHECK FOR DUPLICATE ENTRY IN OPE_data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if ope_doc:
            data_array = ope_doc.get("Data", [])
            for data_item in data_array:
                if formatted_month_range in data_item:
                    entries = data_item[formatted_month_range]
                    for entry in entries:
                        # Check if exact same entry exists (excluding _id, timestamps, and PDF)
                        if (entry.get("date") == date and
                            entry.get("client") == client and
                            entry.get("project_id") == project_id and
                            entry.get("project_name") == project_name and
                            entry.get("project_type") == project_type and
                            entry.get("location_from") == location_from and
                            entry.get("location_to") == location_to and
                            entry.get("travel_mode") == travel_mode and
                            entry.get("amount") == amount):
                            
                            print(f"❌ Duplicate entry detected!")
                            raise HTTPException(
                                status_code=400,
                                detail="⚠️ Duplicate Entry Detected!\n\nAn entry with the same details already exists for this date and month. Please check your entries."
                            )
                    break
        
        # Handle PDF file
        pdf_base64 = None
        if ticket_pdf:
            pdf_content = await ticket_pdf.read()
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            print(f"✅ PDF uploaded: {ticket_pdf.filename}")
        
        # Create entry document
        entry_doc = {
            "_id": ObjectId(),
            "date": date,
            "client": client,
            "project_id": project_id,
            "project_name": project_name,
            "project_type": project_type,
            "location_from": location_from,
            "location_to": location_to,
            "travel_mode": travel_mode,
            "amount": amount,
            "remarks": remarks,
            "ticket_pdf": pdf_base64,
            "created_time": datetime.utcnow().isoformat(),
            "updated_time": datetime.utcnow().isoformat()
        }
        
        print(f"📝 Entry doc created: {entry_doc['date']}")
        
        # Find employee document in OPE_data
        if not ope_doc:
            print(f"🆕 Creating NEW OPE document for {employee_code}")
            # Create new document with FORMATTED month range
            new_doc = {
                "employeeId": employee_code,
                "employeeName": emp.get("Emp Name", ""),
                "designation": emp.get("Designation Name", ""),
                "gender": emp.get("Gender", ""),
                "partner": emp.get("Partner", ""),
                "reportingManager": emp.get("ReportingEmpName", ""),
                "department": "",
                "Data": [
                    {
                        formatted_month_range: [entry_doc]
                    }
                ]
            }
            result = await db["OPE_data"].insert_one(new_doc)
            print(f"✅ NEW document inserted with ID: {result.inserted_id}")
            
        else:
            print(f"📂 Found existing OPE document for {employee_code}")
            # Check if formatted month_range exists in Data
            month_exists = False
            data_array = ope_doc.get("Data", [])
            
            for i, data_item in enumerate(data_array):
                if formatted_month_range in data_item:
                    print(f"✅ Month range '{formatted_month_range}' exists, appending entry")
                    # Append to existing month using $push
                    await db["OPE_data"].update_one(
                        {"employeeId": employee_code},
                        {"$push": {f"Data.{i}.{formatted_month_range}": entry_doc}}
                    )
                    month_exists = True
                    break
            
            if not month_exists:
                print(f"🆕 Month range '{formatted_month_range}' NOT found, creating new")
                # Add new month range using $push with FORMATTED version
                await db["OPE_data"].update_one(
                    {"employeeId": employee_code},
                    {"$push": {"Data": {formatted_month_range: [entry_doc]}}}
                )
        
        print(f"✅✅ Entry submitted successfully!")
        
        # Verify data was saved
        verify_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        print(f"🔍 Verification - Data array length: {len(verify_doc.get('Data', []))}")
        
        return {
            "message": "Entry submitted successfully",
            "employee_id": employee_code,
            "date": date,
            "month_range": formatted_month_range,
            "project_type": project_type,
            "status": "saved"
        }
        
    except HTTPException as he:
        # Re-raise HTTP exceptions as-is
        raise he
    except Exception as e:
        print(f"❌❌ Error submitting OPE entry: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
    
# ---------- GET HISTORY ----------
@app.get("/api/ope/history/{employee_code}")
async def get_ope_history(employee_code: str, current_user=Depends(get_current_user)):
    try:
        print(f"📌 Fetching history for: {employee_code}")
        
        # Verify user can only access their own data
        if current_user["employee_code"] != employee_code:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get employee's OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            return {"history": []}
        
        # Flatten all entries from all month ranges
        history = []
        data_array = ope_doc.get("Data", [])
        
        for data_item in data_array:
            for month_range, entries in data_item.items():
                for entry in entries:
                    history.append({
                        "_id": str(entry.get("_id", "")),
                        "month_range": month_range,
                        "date": entry.get("date"),
                        "client": entry.get("client"),
                        "project_id": entry.get("project_id"),
                        "project_name": entry.get("project_name"),
                        "project_type": entry.get("project_type", "N/A"),  # ✅ NEW FIELD ADDED
                        "location_from": entry.get("location_from"),
                        "location_to": entry.get("location_to"),
                        "travel_mode": entry.get("travel_mode"),
                        "amount": entry.get("amount"),
                        "remarks": entry.get("remarks"),
                        "ticket_pdf": entry.get("ticket_pdf"),
                        "created_time": entry.get("created_time"),
                        "updated_time": entry.get("updated_time")
                    })
        
        print(f"✅ Found {len(history)} entries")
        return {"history": history}
        
    except Exception as e:
        print(f"❌ Error fetching history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------- UPDATE ENTRY ----------
# ---------- UPDATE ENTRY ----------
@app.put("/api/ope/update/{entry_id}")
async def update_ope_entry(
    entry_id: str,
    update_data: dict,  # Assuming you're using dict or Pydantic model
    current_user=Depends(get_current_user)
):
    try:
        employee_code = current_user["employee_code"]
        print(f"📌 Updating entry {entry_id} for: {employee_code}")
        
        # Get month_range from request
        month_range = update_data.get("month_range")
        if not month_range:
            raise HTTPException(status_code=400, detail="month_range required")
        
        # Find the document
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="Employee data not found")
        
        # Find and update the entry
        data_array = ope_doc.get("Data", [])
        updated = False
        
        for i, data_item in enumerate(data_array):
            if month_range in data_item:
                entries = data_item[month_range]
                for j, entry in enumerate(entries):
                    if str(entry.get("_id")) == entry_id:
                        # Update fields
                        update_fields = {
                            f"Data.{i}.{month_range}.{j}.date": update_data.get("date"),
                            f"Data.{i}.{month_range}.{j}.client": update_data.get("client"),
                            f"Data.{i}.{month_range}.{j}.project_id": update_data.get("project_id"),
                            f"Data.{i}.{month_range}.{j}.project_name": update_data.get("project_name"),
                            f"Data.{i}.{month_range}.{j}.project_type": update_data.get("project_type"),  # ✅ NEW FIELD
                            f"Data.{i}.{month_range}.{j}.location_from": update_data.get("location_from"),
                            f"Data.{i}.{month_range}.{j}.location_to": update_data.get("location_to"),
                            f"Data.{i}.{month_range}.{j}.travel_mode": update_data.get("travel_mode"),
                            f"Data.{i}.{month_range}.{j}.amount": update_data.get("amount"),
                            f"Data.{i}.{month_range}.{j}.remarks": update_data.get("remarks"),
                            f"Data.{i}.{month_range}.{j}.updated_time": datetime.utcnow().isoformat()
                        }
                        
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": update_fields}
                        )
                        updated = True
                        break
            if updated:
                break
        
        if not updated:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        print(f"✅ Entry updated successfully")
        return {"message": "Entry updated successfully"}
        
    except Exception as e:
        print(f"❌ Error updating entry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------- DELETE ENTRY ----------
@app.delete("/api/ope/delete/{entry_id}")
async def delete_ope_entry(
    entry_id: str,
    delete_data: dict,  # Contains month_range
    current_user=Depends(get_current_user)
):
    try:
        employee_code = current_user["employee_code"]
        print(f"📌 Deleting entry {entry_id} for: {employee_code}")
        
        # Validate entry_id
        if not entry_id or entry_id == "dummy":
            raise HTTPException(status_code=400, detail="Invalid entry ID")
        
        # Get month_range from request body
        month_range = delete_data.get("month_range")
        if not month_range:
            raise HTTPException(status_code=400, detail="month_range required")
        
        print(f"📌 Month range: {month_range}")
        
        # Find the employee's document
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            raise HTTPException(status_code=404, detail="Employee data not found")
        
        # Find and delete the entry
        data_array = ope_doc.get("Data", [])
        deleted = False
        
        for i, data_item in enumerate(data_array):
            if month_range in data_item:
                entries = data_item[month_range]
                
                # Find the entry with matching _id
                for j, entry in enumerate(entries):
                    if str(entry.get("_id")) == entry_id:
                        print(f"✅ Found entry at Data.{i}.{month_range}.{j}")
                        
                        # If this is the only entry in this month range, remove the entire month
                        if len(entries) == 1:
                            print(f"🗑️ Removing entire month range: {month_range}")
                            await db["OPE_data"].update_one(
                                {"employeeId": employee_code},
                                {"$pull": {"Data": {month_range: {"$exists": True}}}}
                            )
                        else:
                            # Remove only this entry from the array
                            print(f"🗑️ Removing single entry from month range")
                            await db["OPE_data"].update_one(
                                {"employeeId": employee_code},
                                {"$pull": {f"Data.{i}.{month_range}": {"_id": ObjectId(entry_id)}}}
                            )
                        
                        deleted = True
                        break
            
            if deleted:
                break
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        print(f"✅ Entry deleted successfully")
        return {
            "message": "Entry deleted successfully",
            "entry_id": entry_id,
            "month_range": month_range
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error deleting entry: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/check-role/{employee_code}")
async def check_user_role(employee_code: str, current_user=Depends(get_current_user)):
    """
    Check user role: Employee, Reporting Manager, Partner, or HR
    """
    try:
        emp_code = employee_code.strip().upper()
        
        if current_user["employee_code"].upper() != emp_code:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check HR
        is_hr = (emp_code == "JHS729")
        
        # Check Partner
        partner = await db["Partner"].find_one({"PartnerEmpCode": emp_code})
        is_partner = partner is not None
        
        # Check Reporting Manager
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": emp_code})
        is_manager = manager is not None
        
        return {
            "employee_code": emp_code,
            "is_hr": is_hr,
            "is_partner": is_partner,
            "is_manager": is_manager,
            "is_employee": not (is_hr or is_partner or is_manager)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/api/check-manager/{employee_code}")
async def check_if_manager(employee_code: str, current_user=Depends(get_current_user)):
    """
    Check if the logged-in employee is a reporting manager
    """
    try:
        # Clean and uppercase the employee code
        emp_code = employee_code.strip().upper()
        
        print(f"🔍 Checking if {emp_code} is a manager...")
        
        # Verify user can only check their own role
        if current_user["employee_code"].upper() != emp_code:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check in Reporting_managers collection
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": emp_code})
        
        is_manager = manager is not None
        
        if is_manager:
            print(f"✅ {emp_code} IS a reporting manager")
        else:
            print(f"❌ {emp_code} is NOT a reporting manager")
        
        return {
            "employee_code": emp_code,
            "isManager": is_manager,  # ✅ Changed to match your frontend
            "manager_name": manager.get("ReportingEmpName") if manager else None,
            "email": manager.get("Email ID") if manager else None
        }
        
    except Exception as e:
        print(f"❌ Error checking manager role: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ✅ NEW API: Get employees by status (Pending/Approved/Rejected)
@app.get("/api/ope/manager/employees/{status}")
async def get_employees_by_status(
    status: str,  # pending, approved, rejected
    current_user=Depends(get_current_user)
):
    """
    Get all employees under a reporting manager filtered by status
    Status can be: pending, approved, rejected
    """
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"🔍 Fetching {status} employees for manager: {reporting_emp_code}")
        
        # Verify user is a manager
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        # Determine which collection to use based on status
        status_lower = status.lower()
        if status_lower == "pending":
            collection_name = "Pending"
        elif status_lower == "approved":
            collection_name = "Approved"
        elif status_lower == "rejected":
            collection_name = "Rejected"
        else:
            raise HTTPException(status_code=400, detail="Invalid status. Use: pending, approved, or rejected")
        
        # Get status collection document
        status_collection = db[collection_name]
        status_doc = await status_collection.find_one({"ReportingEmpCode": reporting_emp_code})
        
        print(f"📄 Status doc found: {status_doc is not None}")
        
        if not status_doc:
            return {
                "message": f"No {status} data found for manager: {reporting_emp_code}",
                "reporting_manager": reporting_emp_code,
                "employees": []
            }
        
        employee_codes = status_doc.get("EmployeesCodes", [])
        print(f"👥 Employee codes: {employee_codes}")
        
        employees_data = []
        
        # Fetch OPE data for each employee
        for emp_code in employee_codes:
            ope_data = await db["OPE_data"].find_one(
                {"employeeId": emp_code},
                {"_id": 0}
            )
            
            print(f"📊 OPE data for {emp_code}: {ope_data is not None}")
            
            if ope_data:
                employees_data.append({
                    "employeeId": emp_code,
                    "employeeName": ope_data.get("employeeName", ""),
                    "designation": ope_data.get("designation", ""),
                    "opeData": ope_data
                })
            else:
                employees_data.append({
                    "employeeId": emp_code,
                    "employeeName": "Unknown",
                    "designation": "Unknown",
                    "opeData": None
                })
        
        print(f"✅ Returning {len(employees_data)} employees")
        
        return {
            "reporting_manager": reporting_emp_code,
            "status": status_lower,
            "total_employees": len(employees_data),
            "employees": employees_data
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error fetching employees: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

    # ============================================
# EMPLOYEE-SPECIFIC STATUS ENDPOINTS
# ============================================    
@app.get("/api/ope/manager/pending")
async def get_manager_pending_employees(current_user=Depends(get_current_user)):
    """
    Get all employees with pending entries
    - For Reporting Managers: Show entries where status = "pending"
    - For HR (JHS729): Show entries where L1 is approved (or L1 + L2 for 3-level)
    """
    try:
        current_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"\n{'='*60}")
        print(f"🔍 PENDING REQUEST FROM: {current_emp_code}")
        print(f"{'='*60}\n")
        
        # ✅ CHECK IF USER IS HR
        is_hr = (current_emp_code == "JHS729")
        
        if is_hr:
            print(f"👔 USER IS HR - Fetching L1/L2 approved entries")
            
            # ✅ STEP 1: Get ALL Status documents
            all_status_docs = await db["Status"].find({}).to_list(length=None)
            print(f"📊 Total Status documents in DB: {len(all_status_docs)}")
            
            pending_employees = []
            
            # ✅ STEP 2: Process each employee
            for status_doc in all_status_docs:
                employee_id = status_doc.get("employeeId")
                employee_name = status_doc.get("employeeName", "Unknown")
                approval_status = status_doc.get("approval_status", [])
                
                print(f"\n📋 Checking Employee: {employee_id} ({employee_name})")
                print(f"   Total payroll months: {len(approval_status)}")
                
                # Get OPE data for this employee
                ope_doc = await db["OPE_data"].find_one({"employeeId": employee_id})
                
                if not ope_doc:
                    print(f"   ⚠️ No OPE_data found - skipping")
                    continue
                
                pending_entries = []
                
                # ✅ STEP 3: Check each payroll month
                for ps_index, ps in enumerate(approval_status):
                    payroll_month = ps.get("payroll_month")
                    total_levels = ps.get("total_levels", 2)
                    current_level = ps.get("current_level", "L1")
                    overall_status = ps.get("overall_status", "pending")
                    
                    L1 = ps.get("L1", {})
                    L2 = ps.get("L2", {})
                    
                    print(f"\n   📅 Payroll: {payroll_month}")
                    print(f"      Total Levels: {total_levels}")
                    print(f"      Current Level: {current_level}")
                    print(f"      Overall Status: {overall_status}")
                    print(f"      L1 Status: {L1.get('status')}")
                    print(f"      L2 Status: {L2.get('status')}")
                    
                    # ✅ HR LOGIC: Determine if this month should show for HR
                    should_show_to_hr = False
                    
                    # Case 1: 2-level approval (Amount ≤ Limit)
                    if total_levels == 2:
                        # HR should see if: L1 approved AND current_level is L2
                        if L1.get("status") == True and current_level == "L2" and overall_status == "pending":
                            should_show_to_hr = True
                            print(f"      ✅ MATCH: 2-level pending at HR (L1 approved)")
                    
                    # Case 2: 3-level approval (Amount > Limit)
                    elif total_levels == 3:
                        L3 = ps.get("L3", {})
                        print(f"      L3 Status: {L3.get('status')}")
                        
                        # HR should see if: L1 approved AND L2 approved AND current_level is L3
                        if (L1.get("status") == True and 
                            L2.get("status") == True and 
                            current_level == "L3" and 
                            overall_status == "pending"):
                            should_show_to_hr = True
                            print(f"      ✅ MATCH: 3-level pending at HR (L1+L2 approved)")
                    
                    if not should_show_to_hr:
                        print(f"      ❌ NOT for HR - skipping")
                        continue
                    
                    # ✅ STEP 4: Get entries for this payroll month
                    data_array = ope_doc.get("Data", [])
                    
                    for data_item in data_array:
                        if payroll_month in data_item:
                            entries = data_item[payroll_month]
                            print(f"      📦 Found {len(entries)} entries in OPE_data")
                            
                            for entry in entries:
                                entry_status = entry.get("status", "").lower()
                                
                                # ✅ Only show entries with status "approved" by manager
                                if entry_status == "approved":
                                    pending_entries.append({
                                        "_id": str(entry.get("_id", "")),
                                        "month_range": payroll_month,
                                        "date": entry.get("date"),
                                        "client": entry.get("client"),
                                        "project_id": entry.get("project_id"),
                                        "project_name": entry.get("project_name"),
                                        "project_type": entry.get("project_type", "N/A"),
                                        "location_from": entry.get("location_from"),
                                        "location_to": entry.get("location_to"),
                                        "travel_mode": entry.get("travel_mode"),
                                        "amount": entry.get("amount"),
                                        "remarks": entry.get("remarks"),
                                        "ticket_pdf": entry.get("ticket_pdf"),
                                        "total_levels": total_levels,
                                        "current_level": current_level
                                    })
                                    print(f"         ✅ Entry added: {entry.get('date')} - ₹{entry.get('amount')}")
                                else:
                                    print(f"         ⚠️ Entry skipped - status: {entry_status}")
                            
                            break  # Found the month, exit loop
                
                # ✅ STEP 5: Add employee to result if has pending entries
                if pending_entries:
                    pending_employees.append({
                        "employeeId": employee_id,
                        "employeeName": employee_name,
                        "designation": ope_doc.get("designation", ""),
                        "pendingCount": len(pending_entries),
                        "entries": pending_entries
                    })
                    print(f"\n   ✅ ADDED: {employee_name} with {len(pending_entries)} pending entries")
                else:
                    print(f"   ❌ No pending entries for HR")
            
            print(f"\n{'='*60}")
            print(f"✅ FINAL RESULT: {len(pending_employees)} employees pending for HR")
            print(f"{'='*60}\n")
            
            return {
                "reporting_manager": current_emp_code,
                "is_hr": True,
                "total_employees": len(pending_employees),
                "employees": pending_employees
            }
        
        else:
            # ✅ REPORTING MANAGER LOGIC (unchanged)
            print(f"👔 USER IS REPORTING MANAGER")
            
            manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": current_emp_code})
            if not manager:
                raise HTTPException(status_code=403, detail="You are not a reporting manager")
            
            employees = await db["Employee_details"].find(
                {"ReportingEmpCode": current_emp_code}
            ).to_list(length=None)
            
            print(f"👥 Found {len(employees)} employees under manager")
            
            pending_employees = []
            
            for emp in employees:
                emp_code = emp.get("EmpID")
                emp_name = emp.get("Emp Name")
                
                ope_doc = await db["OPE_data"].find_one({"employeeId": emp_code})
                
                if ope_doc:
                    pending_entries = []
                    data_array = ope_doc.get("Data", [])
                    
                    for data_item in data_array:
                        for month_range, entries in data_item.items():
                            for entry in entries:
                                entry_status = entry.get("status", "pending").lower()
                                if entry_status == "pending":
                                    pending_entries.append({
                                        "_id": str(entry.get("_id", "")),
                                        "month_range": month_range,
                                        "date": entry.get("date"),
                                        "client": entry.get("client"),
                                        "project_id": entry.get("project_id"),
                                        "project_name": entry.get("project_name"),
                                        "project_type": entry.get("project_type", "N/A"),
                                        "location_from": entry.get("location_from"),
                                        "location_to": entry.get("location_to"),
                                        "travel_mode": entry.get("travel_mode"),
                                        "amount": entry.get("amount"),
                                        "remarks": entry.get("remarks"),
                                        "ticket_pdf": entry.get("ticket_pdf")
                                    })
                    
                    if pending_entries:
                        pending_employees.append({
                            "employeeId": emp_code,
                            "employeeName": emp_name,
                            "designation": emp.get("Designation Name", ""),
                            "pendingCount": len(pending_entries),
                            "entries": pending_entries
                        })
            
            print(f"✅ Returning {len(pending_employees)} employees for manager")
            
            return {
                "reporting_manager": current_emp_code,
                "is_hr": False,
                "total_employees": len(pending_employees),
                "employees": pending_employees
            }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
# ============================================
# FIXED: GET APPROVED ENTRIES ENDPOINT
# ============================================

@app.get("/api/ope/approved/{employee_code}")
async def get_employee_approved(
    employee_code: str, 
    current_user=Depends(get_current_user)
):
    """
    Get approved entries for a specific employee
    """
    try:
        employee_code = employee_code.strip().upper()
        current_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"\n{'='*60}")
        print(f"📊 GET APPROVED ENTRIES")
        print(f"   Employee: {employee_code}")
        print(f"   Current user: {current_emp_code}")
        print(f"{'='*60}\n")
        
        # ✅ CHECK 1: Is user HR?
        is_hr = (current_emp_code == "JHS729")
        
        # ✅ CHECK 2: Is user accessing their own data?
        is_own_data = (current_emp_code == employee_code)
        
        # ✅ CHECK 3: Is current user a manager?
        is_manager = await db["Reporting_managers"].find_one(
            {"ReportingEmpCode": current_emp_code}
        )
        
        # ✅ ALLOW ACCESS IF: HR, Own Data, OR Manager
        if not (is_hr or is_own_data or is_manager):
            print(f"❌ Access denied - Not HR, not own data, and not a manager")
            raise HTTPException(status_code=403, detail="Access denied")
        
        print(f"✅ Access granted - Fetching OPE data")
        
        # ✅ FETCH OPE DATA
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            print(f"📭 No OPE data found for {employee_code}")
            return {"approved": []}
        
        print(f"✅ OPE document found")
        
        # ✅ FLATTEN AND FILTER APPROVED ENTRIES
        approved_entries = []
        data_array = ope_doc.get("Data", [])
        
        print(f"📊 Total data items: {len(data_array)}")
        
        for data_item in data_array:
            for month_range, entries in data_item.items():
                print(f"   📅 Month: {month_range}, Entries: {len(entries)}")
                
                for entry in entries:
                    entry_status = entry.get("status", "").lower()
                    print(f"      Entry ID: {entry.get('_id')}, Status: '{entry_status}'")
                    
                    # ✅ ONLY APPROVED ENTRIES
                    if entry_status == "approved":
                        approved_entries.append({
                            "_id": str(entry.get("_id", "")),
                            "employee_id": employee_code,
                            "employee_name": ope_doc.get("employeeName", ""),
                            "designation": ope_doc.get("designation", ""),  # ✅ ADDED
                            "month_range": month_range,
                            "date": entry.get("date"),
                            "client": entry.get("client"),
                            "project_id": entry.get("project_id"),
                            "project_name": entry.get("project_name"),
                            "project_type": entry.get("project_type", "N/A"),
                            "location_from": entry.get("location_from"),
                            "location_to": entry.get("location_to"),
                            "travel_mode": entry.get("travel_mode"),
                            "amount": entry.get("amount"),
                            "remarks": entry.get("remarks"),
                            "ticket_pdf": entry.get("ticket_pdf"),
                            "approved_by": entry.get("approved_by"),
                            "approver_name": entry.get("approver_name"),
                            "approved_date": entry.get("approved_date"),
                            "created_time": entry.get("created_time")
                        })
                        print(f"      ✅ APPROVED entry added")
        
        print(f"\n✅ Total approved entries found: {len(approved_entries)}\n")
        return {"approved": approved_entries}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"\n❌❌ ERROR fetching approved:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/api/ope/rejected/{employee_code}")
async def get_employee_rejected(
    employee_code: str, 
    current_user=Depends(get_current_user)
):
    """
    Get rejected entries for a specific employee
    """
    try:
        employee_code = employee_code.strip().upper()
        current_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"\n{'='*60}")
        print(f"❌ GET REJECTED ENTRIES")
        print(f"   Employee: {employee_code}")
        print(f"   Current user: {current_emp_code}")
        print(f"{'='*60}\n")
        
        # ✅ CHECK 1: Is user HR?
        is_hr = (current_emp_code == "JHS729")
        
        # ✅ CHECK 2: Is user accessing their own data?
        is_own_data = (current_emp_code == employee_code)
        
        # ✅ CHECK 3: Is current user a manager?
        is_manager = await db["Reporting_managers"].find_one(
            {"ReportingEmpCode": current_emp_code}
        )
        
        # ✅ ALLOW ACCESS IF: HR, Own Data, OR Manager
        if not (is_hr or is_own_data or is_manager):
            print(f"❌ Access denied")
            raise HTTPException(status_code=403, detail="Access denied")
        
        print(f"✅ Access granted - Fetching OPE data")
        
        # ✅ FETCH OPE DATA
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            print(f"📭 No OPE data found for {employee_code}")
            return {"rejected": []}
        
        print(f"✅ OPE document found")
        
        # ✅ FLATTEN AND FILTER REJECTED ENTRIES
        rejected_entries = []
        data_array = ope_doc.get("Data", [])
        
        print(f"📊 Total data items: {len(data_array)}")
        
        for data_item in data_array:
            for month_range, entries in data_item.items():
                print(f"   📅 Month: {month_range}, Entries: {len(entries)}")
                
                for entry in entries:
                    entry_status = entry.get("status", "").lower()
                    print(f"      Entry ID: {entry.get('_id')}, Status: '{entry_status}'")
                    
                    # ✅ ONLY REJECTED ENTRIES
                    if entry_status == "rejected":
                        rejected_entries.append({
                            "_id": str(entry.get("_id", "")),
                            "employee_id": employee_code,
                            "employee_name": ope_doc.get("employeeName", ""),
                            "designation": ope_doc.get("designation", ""),  # ✅ ADDED
                            "month_range": month_range,
                            "date": entry.get("date"),
                            "client": entry.get("client"),
                            "project_id": entry.get("project_id"),
                            "project_name": entry.get("project_name"),
                            "project_type": entry.get("project_type", "N/A"),
                            "location_from": entry.get("location_from"),
                            "location_to": entry.get("location_to"),
                            "travel_mode": entry.get("travel_mode"),
                            "amount": entry.get("amount"),
                            "remarks": entry.get("remarks"),
                            "ticket_pdf": entry.get("ticket_pdf"),
                            "rejected_by": entry.get("rejected_by"),
                            "rejector_name": entry.get("rejector_name"),
                            "rejected_date": entry.get("rejected_date"),
                            "rejection_reason": entry.get("rejection_reason"),
                            "rejected_level": entry.get("rejected_level"),  # ✅ ADDED
                            "created_time": entry.get("created_time")
                        })
                        print(f"      ✅ REJECTED entry added")
        
        print(f"\n✅ Total rejected entries found: {len(rejected_entries)}\n")
        return {"rejected": rejected_entries}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"\n❌❌ ERROR fetching rejected:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/ope/manager/reject/{employee_code}")
async def reject_employee_entries(
    employee_code: str,
    request: Request,
    current_user=Depends(get_current_user)
):
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        body = await request.json()
        rejection_reason = body.get("reason", "No reason provided")
        
        print(f"\n{'='*60}")
        print(f"❌ REJECTING EMPLOYEE")
        print(f"Manager: {reporting_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"Reason: {rejection_reason}")
        print(f"{'='*60}\n")
        
        # Get manager details
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        manager_name = manager.get("ReportingEmpName", reporting_emp_code)
        
        # Get employee details
        emp = await db["Employee_details"].find_one({"EmpID": employee_code})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        emp_reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
        
        # Get OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No data found")
        
        data_array = ope_doc.get("Data", [])
        rejected_count = 0
        current_time = datetime.utcnow().isoformat()
        
        # ✅ UPDATE ALL PENDING ENTRIES TO REJECTED
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    if entry.get("status", "").lower() == "pending":
                        # Update entry status
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "rejected",
                                f"Data.{i}.{month_range}.{j}.rejected_by": reporting_emp_code,
                                f"Data.{i}.{month_range}.{j}.rejector_name": manager_name,  # ✅ KEY FIX
                                f"Data.{i}.{month_range}.{j}.rejected_date": current_time,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": rejection_reason
                            }}
                        )
                        
                        # Update Status collection
                        status_id = entry.get("status_id")
                        if status_id:
                            await db["Status"].update_one(
                                {"_id": ObjectId(status_id)},
                                {"$set": {
                                    "overall_status": "rejected",
                                    "L1.status": False,
                                    "L1.rejected_by": reporting_emp_code,
                                    "L1.rejected_date": current_time
                                }}
                            )
                        
                        rejected_count += 1
                        print(f"✅ Rejected entry {j + 1}")
        
        if rejected_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found")
        
        print(f"\n✅ Total entries rejected: {rejected_count}")
        
        # ✅ REMOVE FROM PENDING
        await db["Pending"].update_one(
            {"ReportingEmpCode": emp_reporting_manager_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        print(f"✅ Removed from Pending collection")
        
        # ✅ ADD TO REJECTED (UNDER CURRENT MANAGER'S CODE)
        rejected_doc = await db["Rejected"].find_one({"ReportingEmpCode": reporting_emp_code})
        
        if not rejected_doc:
            await db["Rejected"].insert_one({
                "ReportingEmpCode": reporting_emp_code,
                "EmployeesCodes": [employee_code]
            })
            print(f"✅ Created NEW Rejected document")
        else:
            if employee_code not in rejected_doc.get("EmployeesCodes", []):
                await db["Rejected"].update_one(
                    {"ReportingEmpCode": reporting_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
                print(f"✅ Added to Rejected collection")
            else:
                print(f"⚠️ Employee already in Rejected collection")
        
        print(f"{'='*60}\n")
        
        return {
            "message": f"Rejected {rejected_count} entries",
            "rejected_count": rejected_count,
            "rejection_reason": rejection_reason,
            "employee_code": employee_code
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))  


# ============================================
# EDIT ENTRY AMOUNT (Manager/Partner/HR)
# ============================================
@app.put("/api/ope/manager/edit-amount")
async def edit_entry_amount(
    request: Request,
    current_user=Depends(get_current_user)
):
    """
    Edit the amount of a pending, approved, or rejected entry
    """
    try:
        manager_emp_code = current_user["employee_code"].strip().upper()
        
        body = await request.json()
        entry_id = body.get("entry_id")
        employee_id = body.get("employee_id")
        new_amount = body.get("new_amount")
        
        print(f"\n{'='*60}")
        print(f"💰 EDIT AMOUNT REQUEST")
        print(f"   Manager: {manager_emp_code}")
        print(f"   Employee: {employee_id}")
        print(f"   Entry ID: {entry_id}")
        print(f"   New Amount: {new_amount}")
        print(f"{'='*60}\n")
        
        # Validate inputs
        if not entry_id or not employee_id or new_amount is None:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        if new_amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")
        
        # Verify manager has permission
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": manager_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        # Get employee details
        emp = await db["Employee_details"].find_one({"EmpID": employee_id})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Find and update the entry in OPE_data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_id})
        
        if not ope_doc:
            raise HTTPException(status_code=404, detail="Employee data not found")
        
        data_array = ope_doc.get("Data", [])
        updated = False
        old_amount = 0
        payroll_month = None
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    if str(entry.get("_id")) == entry_id:
                        old_amount = entry.get("amount", 0)
                        payroll_month = month_range
                        
                        # ✅ UPDATE ENTRY AMOUNT
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_id},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.amount": new_amount,
                                f"Data.{i}.{month_range}.{j}.updated_time": datetime.utcnow().isoformat(),
                                f"Data.{i}.{month_range}.{j}.amount_edited_by": manager_emp_code,
                                f"Data.{i}.{month_range}.{j}.amount_edited_date": datetime.utcnow().isoformat()
                            }}
                        )
                        
                        updated = True
                        print(f"✅ Amount updated: ₹{old_amount} → ₹{new_amount}")
                        break
            if updated:
                break
        
        if not updated:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        # ✅ UPDATE STATUS COLLECTION - RECALCULATE TOTAL AMOUNT
        if payroll_month:
            status_doc = await db["Status"].find_one({"employeeId": employee_id})
            
            if status_doc:
                approval_status = status_doc.get("approval_status", [])
                
                # Recalculate total for this payroll month
                new_total = 0
                for i, data_item in enumerate(data_array):
                    if payroll_month in data_item:
                        entries = data_item[payroll_month]
                        new_total = sum(float(e.get("amount", 0)) for e in entries)
                        break
                
                # Update Status collection
                for i, ps in enumerate(approval_status):
                    if ps.get("payroll_month") == payroll_month:
                        await db["Status"].update_one(
                            {"employeeId": employee_id},
                            {"$set": {
                                f"approval_status.{i}.total_amount": new_total
                            }}
                        )
                        print(f"✅ Updated Status total_amount to: ₹{new_total}")
                        break
        
        print(f"{'='*60}\n")
        
        return {
            "message": "Amount updated successfully",
            "old_amount": old_amount,
            "new_amount": new_amount,
            "entry_id": entry_id
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error editing amount: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))     

# ============================================
# EDIT TOTAL AMOUNT FOR ENTIRE MONTH (Proportional Distribution)
# ============================================
@app.put("/api/ope/manager/edit-total-amount")
async def edit_total_amount(
    request: Request,
    current_user=Depends(get_current_user)
):
    """
    Edit total amount for a month - proportionally distributes to all entries
    """
    try:
        manager_emp_code = current_user["employee_code"].strip().upper()
        
        body = await request.json()
        employee_id = body.get("employee_id")
        month_range = body.get("month_range")
        new_total = body.get("new_total")
        
        print(f"\n{'='*60}")
        print(f"💰💰 EDIT TOTAL AMOUNT REQUEST")
        print(f"   Manager: {manager_emp_code}")
        print(f"   Employee: {employee_id}")
        print(f"   Month: {month_range}")
        print(f"   New Total: ₹{new_total}")
        print(f"{'='*60}\n")
        
        # Validate inputs
        if not employee_id or not month_range or new_total is None:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        if new_total <= 0:
            raise HTTPException(status_code=400, detail="Total amount must be greater than 0")
        
        # Verify manager has permission
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": manager_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        # Find employee's OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_id})
        
        if not ope_doc:
            raise HTTPException(status_code=404, detail="Employee data not found")
        
        data_array = ope_doc.get("Data", [])
        entries_found = []
        data_index = None
        old_total = 0
        
        # Find the month's entries
        for i, data_item in enumerate(data_array):
            if month_range in data_item:
                entries_found = data_item[month_range]
                data_index = i
                old_total = sum(float(e.get("amount", 0)) for e in entries_found)
                break
        
        if not entries_found:
            raise HTTPException(status_code=404, detail="No entries found for this month")
        
        print(f"📊 Found {len(entries_found)} entries")
        print(f"💵 Old Total: ₹{old_total}")
        print(f"💵 New Total: ₹{new_total}")
        
        # ✅ CALCULATE PROPORTIONAL DISTRIBUTION
        entries_updated = 0
        
        if old_total > 0:
            # Proportional distribution based on original amounts
            ratio = new_total / old_total
            print(f"📐 Distribution ratio: {ratio:.4f}")
            
            for j, entry in enumerate(entries_found):
                old_amount = float(entry.get("amount", 0))
                new_amount = round(old_amount * ratio, 2)
                
                # Update entry
                await db["OPE_data"].update_one(
                    {"employeeId": employee_id},
                    {"$set": {
                        f"Data.{data_index}.{month_range}.{j}.amount": new_amount,
                        f"Data.{data_index}.{month_range}.{j}.updated_time": datetime.utcnow().isoformat(),
                        f"Data.{data_index}.{month_range}.{j}.amount_edited_by": manager_emp_code,
                        f"Data.{data_index}.{month_range}.{j}.amount_edited_date": datetime.utcnow().isoformat(),
                        f"Data.{data_index}.{month_range}.{j}.original_amount": old_amount
                    }}
                )
                
                entries_updated += 1
                print(f"   Entry {j+1}: ₹{old_amount} → ₹{new_amount}")
        else:
            # If old total is 0, distribute equally
            amount_per_entry = round(new_total / len(entries_found), 2)
            print(f"📐 Equal distribution: ₹{amount_per_entry} per entry")
            
            for j, entry in enumerate(entries_found):
                await db["OPE_data"].update_one(
                    {"employeeId": employee_id},
                    {"$set": {
                        f"Data.{data_index}.{month_range}.{j}.amount": amount_per_entry,
                        f"Data.{data_index}.{month_range}.{j}.updated_time": datetime.utcnow().isoformat(),
                        f"Data.{data_index}.{month_range}.{j}.amount_edited_by": manager_emp_code,
                        f"Data.{data_index}.{month_range}.{j}.amount_edited_date": datetime.utcnow().isoformat(),
                        f"Data.{data_index}.{month_range}.{j}.original_amount": 0
                    }}
                )
                
                entries_updated += 1
                print(f"   Entry {j+1}: ₹0 → ₹{amount_per_entry}")
        
        # ✅ UPDATE STATUS COLLECTION
        status_doc = await db["Status"].find_one({"employeeId": employee_id})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") == month_range:
                    await db["Status"].update_one(
                        {"employeeId": employee_id},
                        {"$set": {
                            f"approval_status.{i}.total_amount": new_total,
                            f"approval_status.{i}.total_edited_by": manager_emp_code,
                            f"approval_status.{i}.total_edited_date": datetime.utcnow().isoformat()
                        }}
                    )
                    print(f"✅ Updated Status collection total_amount")
                    break
        
        print(f"\n✅✅ TOTAL AMOUNT UPDATE COMPLETE")
        print(f"   Entries updated: {entries_updated}")
        print(f"   Old Total: ₹{old_total}")
        print(f"   New Total: ₹{new_total}")
        print(f"{'='*60}\n")
        
        return {
            "message": "Total amount updated successfully",
            "old_total": old_total,
            "new_total": new_total,
            "entries_updated": entries_updated,
            "distribution_method": "proportional" if old_total > 0 else "equal"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error editing total amount: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) 

# ==================================================
# TEMPORARY SAVE ENDPOINT (Store in Temp_OPE_data)
# ==================================================
@app.post("/api/ope/save-temp")
async def save_temp_entry(
    date: str = Form(...),
    client: str = Form(...),
    project_id: str = Form(...),
    project_name: str = Form(...),
    project_type: str = Form(...),
    location_from: str = Form(...),
    location_to: str = Form(...),
    travel_mode: str = Form(...),
    amount: float = Form(...),
    remarks: str = Form(...),
    month_range: str = Form(...),
    ticket_pdf: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user)
):
    try:
        employee_code = current_user["employee_code"]
        
        print(f"💾 Saving temporary entry for: {employee_code}")
        
        # Get employee details
        emp = await db["Employee_details"].find_one({"EmpID": employee_code})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Format month_range
        def format_month_range(month_str):
            try:
                parts = month_str.lower().split('-')
                month_map = {
                    'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
                    'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
                    'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
                }
                
                if len(parts) == 3:
                    month1 = month_map.get(parts[0], parts[0].capitalize())
                    month2 = month_map.get(parts[1], parts[1].capitalize())
                    year = parts[2]
                    return f"{month1} {year} - {month2} {year}"
                elif len(parts) == 2:
                    month = month_map.get(parts[0], parts[0].capitalize())
                    year = parts[1]
                    return f"{month} {year}"
                else:
                    return month_str
            except Exception as e:
                return month_str
        
        formatted_month_range = format_month_range(month_range)
        
        # ✅ CHECK FOR DUPLICATE ENTRY IN TEMP_OPE_data
        temp_doc = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        
        if temp_doc:
            data_array = temp_doc.get("Data", [])
            for data_item in data_array:
                if formatted_month_range in data_item:
                    entries = data_item[formatted_month_range]
                    for entry in entries:
                        # Check if exact same entry exists (excluding _id, timestamps, and PDF)
                        if (entry.get("date") == date and
                            entry.get("client") == client and
                            entry.get("project_id") == project_id and
                            entry.get("project_name") == project_name and
                            entry.get("project_type") == project_type and
                            entry.get("location_from") == location_from and
                            entry.get("location_to") == location_to and
                            entry.get("travel_mode") == travel_mode and
                            entry.get("amount") == amount):
                            
                            raise HTTPException(
                                status_code=400,
                                detail="⚠️ Duplicate Entry Detected!\n\nAn entry with the same details already exists for this date and month."
                            )
        
        # Handle PDF
        pdf_base64 = None
        if ticket_pdf:
            pdf_content = await ticket_pdf.read()
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
        
        # Create entry
        entry_doc = {
            "_id": ObjectId(),
            "date": date,
            "client": client,
            "project_id": project_id,
            "project_name": project_name,
            "project_type": project_type,
            "location_from": location_from,
            "location_to": location_to,
            "travel_mode": travel_mode,
            "amount": amount,
            "remarks": remarks,
            "ticket_pdf": pdf_base64,
            "created_time": datetime.utcnow().isoformat(),
            "updated_time": datetime.utcnow().isoformat(),
            "status": "saved"
        }
        
        # Find or create document in Temp_OPE_data
        if not temp_doc:
            new_doc = {
                "employeeId": employee_code,
                "employeeName": emp.get("Emp Name", ""),
                "designation": emp.get("Designation Name", ""),
                "gender": emp.get("Gender", ""),
                "partner": emp.get("Partner", ""),
                "reportingManager": emp.get("ReportingEmpName", ""),
                "department": "",
                "Data": [
                    {
                        formatted_month_range: [entry_doc]
                    }
                ]
            }
            await db["Temp_OPE_data"].insert_one(new_doc)
            print(f"✅ NEW temp document created")
        else:
            # Check if month exists
            month_exists = False
            data_array = temp_doc.get("Data", [])
            
            for i, data_item in enumerate(data_array):
                if formatted_month_range in data_item:
                    await db["Temp_OPE_data"].update_one(
                        {"employeeId": employee_code},
                        {"$push": {f"Data.{i}.{formatted_month_range}": entry_doc}}
                    )
                    month_exists = True
                    break
            
            if not month_exists:
                await db["Temp_OPE_data"].update_one(
                    {"employeeId": employee_code},
                    {"$push": {"Data": {formatted_month_range: [entry_doc]}}}
                )
        
        print(f"✅ Entry saved temporarily")
        return {
            "message": "Entry saved temporarily",
            "entry_id": str(entry_doc["_id"]),
            "status": "saved"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error saving temp entry: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ========================
# GET TEMPORARY HISTORY
# =========================
@app.get("/api/ope/temp-history/{employee_code}")
async def get_temp_history(employee_code: str, current_user=Depends(get_current_user)):
    try:
        print(f"📌 Fetching temp history for: {employee_code}")
        
        if current_user["employee_code"] != employee_code:
            raise HTTPException(status_code=403, detail="Access denied")
        
        temp_doc = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        
        if not temp_doc:
            print(f"📭 No temp data found")
            return {"history": []}
        
        history = []
        data_array = temp_doc.get("Data", [])
        
        for data_item in data_array:
            for month_range, entries in data_item.items():
                for entry in entries:
                    history.append({
                        "_id": str(entry.get("_id", "")),
                        "month_range": month_range,
                        "date": entry.get("date"),
                        "client": entry.get("client"),
                        "project_id": entry.get("project_id"),
                        "project_name": entry.get("project_name"),
                        "project_type": entry.get("project_type", "N/A"),
                        "location_from": entry.get("location_from"),
                        "location_to": entry.get("location_to"),
                        "travel_mode": entry.get("travel_mode"),
                        "amount": entry.get("amount"),
                        "remarks": entry.get("remarks"),
                        "ticket_pdf": entry.get("ticket_pdf"),
                        "status": "saved"
                    })
        
        print(f"✅ Found {len(history)} temp entries")
        return {"history": history}
        
    except Exception as e:
        print(f"❌ Error fetching temp history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================
# UPDATE TEMPORARY ENTRY
# ========================
@app.put("/api/ope/update-temp/{entry_id}")
async def update_temp_entry(
    entry_id: str,
    update_data: dict,
    current_user=Depends(get_current_user)
):
    try:
        employee_code = current_user["employee_code"]
        month_range = update_data.get("month_range")
        
        print(f"📝 Updating temp entry {entry_id} for: {employee_code}")
        
        if not month_range:
            raise HTTPException(status_code=400, detail="month_range required")
        
        temp_doc = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        if not temp_doc:
            raise HTTPException(status_code=404, detail="No temporary data found")
        
        data_array = temp_doc.get("Data", [])
        updated = False
        
        for i, data_item in enumerate(data_array):
            if month_range in data_item:
                entries = data_item[month_range]
                for j, entry in enumerate(entries):
                    if str(entry.get("_id")) == entry_id:
                        update_fields = {
                            f"Data.{i}.{month_range}.{j}.date": update_data.get("date"),
                            f"Data.{i}.{month_range}.{j}.client": update_data.get("client"),
                            f"Data.{i}.{month_range}.{j}.project_id": update_data.get("project_id"),
                            f"Data.{i}.{month_range}.{j}.project_name": update_data.get("project_name"),
                            f"Data.{i}.{month_range}.{j}.project_type": update_data.get("project_type"),
                            f"Data.{i}.{month_range}.{j}.location_from": update_data.get("location_from"),
                            f"Data.{i}.{month_range}.{j}.location_to": update_data.get("location_to"),
                            f"Data.{i}.{month_range}.{j}.travel_mode": update_data.get("travel_mode"),
                            f"Data.{i}.{month_range}.{j}.amount": update_data.get("amount"),
                            f"Data.{i}.{month_range}.{j}.remarks": update_data.get("remarks"),
                            f"Data.{i}.{month_range}.{j}.updated_time": datetime.utcnow().isoformat()
                        }
                        
                        await db["Temp_OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": update_fields}
                        )
                        updated = True
                        print(f"✅ Entry updated successfully")
                        break
            if updated:
                break
        
        if not updated:
            raise HTTPException(status_code=404, detail="Entry not found in temp data")
        
        return {"message": "Entry updated successfully"}
        
    except Exception as e:
        print(f"❌ Error updating temp entry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DELETE TEMPORARY ENTRY
# ============================================
@app.delete("/api/ope/delete-temp/{entry_id}")
async def delete_temp_entry(
    entry_id: str,
    delete_data: dict,
    current_user=Depends(get_current_user)
):
    try:
        employee_code = current_user["employee_code"]
        month_range = delete_data.get("month_range")
        
        print(f"🗑️ Deleting temp entry {entry_id} for: {employee_code}")
        
        if not entry_id or entry_id == "dummy":
            raise HTTPException(status_code=400, detail="Invalid entry ID")
        
        if not month_range:
            raise HTTPException(status_code=400, detail="month_range required")
        
        temp_doc = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        if not temp_doc:
            raise HTTPException(status_code=404, detail="No temporary data found")
        
        data_array = temp_doc.get("Data", [])
        deleted = False
        
        for i, data_item in enumerate(data_array):
            if month_range in data_item:
                entries = data_item[month_range]
                
                for j, entry in enumerate(entries):
                    if str(entry.get("_id")) == entry_id:
                        print(f"✅ Found entry at Data.{i}.{month_range}.{j}")
                        
                        # If only entry in month, remove entire month
                        if len(entries) == 1:
                            print(f"🗑️ Removing entire month range")
                            await db["Temp_OPE_data"].update_one(
                                {"employeeId": employee_code},
                                {"$pull": {"Data": {month_range: {"$exists": True}}}}
                            )
                        else:
                            # Remove only this entry
                            print(f"🗑️ Removing single entry")
                            await db["Temp_OPE_data"].update_one(
                                {"employeeId": employee_code},
                                {"$pull": {f"Data.{i}.{month_range}": {"_id": ObjectId(entry_id)}}}
                            )
                        
                        deleted = True
                        break
            
            if deleted:
                break
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Entry not found in temp data")
        
        print(f"✅ Entry deleted successfully")
        return {
            "message": "Entry deleted successfully",
            "entry_id": entry_id
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error deleting temp entry: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

            
# ============================================
# SUBMIT ALL ENTRIES - COMPLETE UPDATED VERSION
# ============================================
@app.post("/api/ope/submit-final")
async def submit_final_entries(
    request: Request,
    current_user=Depends(get_current_user)
):
    try:
        employee_code = current_user["employee_code"].strip().upper()
        
        body = await request.json()
        month_range = body.get("month_range")
        
        print(f"🚀 SUBMIT FINAL: Employee {employee_code}, Month {month_range}")
        
        if not month_range:
            raise HTTPException(status_code=400, detail="month_range required")
        
        def format_month_range(month_str):
            try:
                parts = month_str.lower().split('-')
                month_map = {
                    'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
                    'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
                    'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
                }
                
                if len(parts) == 3:
                    month1 = month_map.get(parts[0], parts[0].capitalize())
                    month2 = month_map.get(parts[1], parts[1].capitalize())
                    year = parts[2]
                    return f"{month1} {year} - {month2} {year}"
                elif len(parts) == 2:
                    month = month_map.get(parts[0], parts[0].capitalize())
                    year = parts[1]
                    return f"{month} {year}"
                else:
                    return month_str
            except Exception as e:
                return month_str
        
        formatted_month_range = format_month_range(month_range)
        print(f"📅 Formatted month range: {formatted_month_range}")
        
        # Get temp data
        temp_doc = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        
        if not temp_doc:
            raise HTTPException(status_code=404, detail="No temporary data found to submit")
        
        entries_to_submit = []
        data_array = temp_doc.get("Data", [])
        
        for data_item in data_array:
            if formatted_month_range in data_item:
                entries_to_submit = data_item[formatted_month_range]
                break
        
        if not entries_to_submit:
            raise HTTPException(status_code=404, detail=f"No entries found for {formatted_month_range}")
        
        print(f"📦 Found {len(entries_to_submit)} entries to submit")
        
        # Get employee details
        emp = await db["Employee_details"].find_one({"EmpID": employee_code})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee details not found")
        
        # ✅ GET OPE LIMIT FROM EMPLOYEE DETAILS COLLECTION (NOT HARDCODED)
        ope_limit = emp.get("OPE LIMIT")
        
        # ✅ FALLBACK TO 5000 IF NOT FOUND IN DATABASE
        if ope_limit is None:
            ope_limit = 1500
            print(f"⚠️ OPE Limit not found in Employee_details, using default: ₹{ope_limit}")
        else:
            ope_limit = float(ope_limit)
            print(f"✅ OPE Limit from Employee_details: ₹{ope_limit}")
        
        reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
        reporting_manager_name = emp.get("ReportingEmpName", "")
        partner_code = emp.get("PartnerEmpCode", "").strip().upper()
        partner_name = emp.get("Partner", "")
        
        if not reporting_manager_code:
            raise HTTPException(status_code=400, detail="No reporting manager assigned")
        
        print(f"👔 Reporting Manager: {reporting_manager_code} ({reporting_manager_name})")
        print(f"👔 Partner: {partner_code} ({partner_name})")
        
        # ✅ CALCULATE TOTAL AMOUNT FOR NEW ENTRIES
        new_entries_amount = sum(float(entry.get("amount", 0)) for entry in entries_to_submit)
        
        print(f"💰 New entries amount: ₹{new_entries_amount}")
        print(f"🎯 Employee's OPE Limit: ₹{ope_limit}")
        
        # ✅ CHECK IF STATUS DOCUMENT EXISTS AND GET EXISTING TOTAL
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        existing_total = 0
        month_exists = False
        existing_month_index = -1
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") == formatted_month_range:
                    # ✅ MONTH EXISTS - Get existing total
                    existing_total = ps.get("total_amount", 0)
                    month_exists = True
                    existing_month_index = i
                    print(f"📊 Found existing month entry with total: ₹{existing_total}")
                    break
        
        # ✅ CALCULATE CUMULATIVE TOTAL
        cumulative_total = existing_total + new_entries_amount
        
        print(f"\n{'='*60}")
        print(f"💰 AMOUNT CALCULATION:")
        print(f"   Previous Total: ₹{existing_total}")
        print(f"   New Entries: +₹{new_entries_amount}")
        print(f"   Cumulative Total: ₹{cumulative_total}")
        print(f"   OPE Limit: ₹{ope_limit}")
        print(f"{'='*60}\n")
        
        # ✅ DYNAMIC APPROVAL LEVELS BASED ON CUMULATIVE TOTAL VS LIMIT
        if cumulative_total > ope_limit:
            ope_label = "Greater"
            total_levels = 3
            print(f"📊 Cumulative amount (₹{cumulative_total}) EXCEEDS limit (₹{ope_limit}) → 3-level approval required")
        else:
            ope_label = "Less"
            total_levels = 2
            print(f"📊 Cumulative amount (₹{cumulative_total}) WITHIN limit (₹{ope_limit}) → 2-level approval required")
        
        current_time = datetime.utcnow().isoformat()
        
        # ✅ CREATE PAYROLL ENTRY WITH CUMULATIVE TOTAL
        payroll_entry = {
            "payroll_month": formatted_month_range,
            "ope_label": ope_label,
            "total_levels": total_levels,
            "limit": ope_limit,  # ✅ Store employee's actual OPE limit
            "total_amount": cumulative_total,
            "L1": {
                "status": False,
                "approver_name": reporting_manager_name,
                "approver_code": reporting_manager_code,
                "approved_date": None,
                "level_name": "Reporting Manager"
            },
            "L2": {
                "status": False,
                "approver_name": "HR" if total_levels == 2 else partner_name,
                "approver_code": "JHS729" if total_levels == 2 else partner_code,
                "approved_date": None,
                "level_name": "HR" if total_levels == 2 else "Partner"
            },
            "current_level": "L1",
            "overall_status": "pending",
            "submission_date": current_time
        }
        
        # ✅ ADD L3 ONLY IF TOTAL_LEVELS = 3 (Amount > Limit)
        if total_levels == 3:
            payroll_entry["L3"] = {
                "status": False,
                "approver_name": "HR",
                "approver_code": "JHS729",
                "approved_date": None,
                "level_name": "HR"
            }
            print(f"✅ Added L3 (HR) level for approval")
        
        # ✅ CREATE OR UPDATE STATUS DOCUMENT
        # ✅ CREATE OR UPDATE STATUS DOCUMENT
        if not status_doc:
            # ✅ CREATE NEW STATUS DOCUMENT
            new_status_doc = {
                "employeeId": employee_code,
                "employeeName": emp.get("Emp Name", ""),
                "ReportingEmpCode": reporting_manager_code, 
                "PartnerEmpCode": partner_code,  
                "HREmpCode": "JHS729", 
                "approval_status": [payroll_entry]
            }
            result = await db["Status"].insert_one(new_status_doc)
            status_doc_id = str(result.inserted_id)
            
        else:
            # ✅ UPDATE EXISTING STATUS DOCUMENT
            status_doc_id = str(status_doc["_id"])
            
            if month_exists:
                # ✅ UPDATE EXISTING MONTH WITH CUMULATIVE TOTAL
                print(f"🔄 Updating existing month entry at index {existing_month_index}")
                
                update_fields = {
                    f"approval_status.{existing_month_index}.total_amount": cumulative_total,
                    f"approval_status.{existing_month_index}.ope_label": ope_label,
                    f"approval_status.{existing_month_index}.total_levels": total_levels,
                    f"approval_status.{existing_month_index}.limit": ope_limit, 
                    f"approval_status.{existing_month_index}.submission_date": current_time
                }
                
                # ✅ Update L2 and Add L3 if total_levels changed from 2 to 3
                if total_levels == 3:
                    update_fields[f"approval_status.{existing_month_index}.L3"] = {
                        "status": False,
                        "approver_name": "HR",
                        "approver_code": "JHS729",
                        "approved_date": None,
                        "level_name": "HR"
                    }
                    update_fields[f"approval_status.{existing_month_index}.L2.approver_name"] = partner_name
                    update_fields[f"approval_status.{existing_month_index}.L2.approver_code"] = partner_code
                    update_fields[f"approval_status.{existing_month_index}.L2.level_name"] = "Partner"
                else:
                    update_fields[f"approval_status.{existing_month_index}.L2.approver_name"] = "HR"
                    update_fields[f"approval_status.{existing_month_index}.L2.approver_code"] = "JHS729"
                    update_fields[f"approval_status.{existing_month_index}.L2.level_name"] = "HR"
                
                await db["Status"].update_one(
                    {"employeeId": employee_code},
                    {"$set": update_fields}
                )
                
                print(f"✅ Updated existing payroll month with cumulative total: ₹{cumulative_total}")
                
            else:
                # ✅ ADD NEW PAYROLL MONTH
                await db["Status"].update_one(
                    {"employeeId": employee_code},
                    {"$push": {"approval_status": payroll_entry}}
                )
                print(f"✅ Added new payroll month: {formatted_month_range}")
        
        # ✅ UPDATE EACH ENTRY WITH STATUS REFERENCE
        for entry in entries_to_submit:
            entry["status"] = "pending"
            entry["submitted_time"] = current_time
            entry["status_doc_id"] = status_doc_id
            entry["payroll_month"] = formatted_month_range
            entry["approved_by"] = None
            entry["approved_date"] = None
            entry["rejected_by"] = None
            entry["rejected_date"] = None
            entry["rejection_reason"] = None
        
        # ✅ Move to OPE_data collection
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            new_doc = {
                "employeeId": employee_code,
                "employeeName": emp.get("Emp Name", ""),
                "designation": emp.get("Designation Name", ""),
                "gender": emp.get("Gender", ""),
                "partner": emp.get("Partner", ""),
                "reportingManager": emp.get("ReportingEmpName", ""),
                "department": "",
                "Data": [
                    {
                        formatted_month_range: entries_to_submit
                    }
                ]
            }
            await db["OPE_data"].insert_one(new_doc)
            print(f"✅ Created new OPE_data document")
        else:
            month_exists_in_ope = False
            ope_data_array = ope_doc.get("Data", [])
            
            for i, data_item in enumerate(ope_data_array):
                if formatted_month_range in data_item:
                    for entry in entries_to_submit:
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$push": {f"Data.{i}.{formatted_month_range}": entry}}
                        )
                    month_exists_in_ope = True
                    print(f"✅ Appended to existing month in OPE_data")
                    break
            
            if not month_exists_in_ope:
                await db["OPE_data"].update_one(
                    {"employeeId": employee_code},
                    {"$push": {"Data": {formatted_month_range: entries_to_submit}}}
                )
                print(f"✅ Added new month range to OPE_data")
        
        # ✅ Add to PENDING collection
        pending_doc = await db["Pending"].find_one({"ReportingEmpCode": reporting_manager_code})
        
        if not pending_doc:
            await db["Pending"].insert_one({
                "ReportingEmpCode": reporting_manager_code,
                "EmployeesCodes": [employee_code]
            })
            print(f"✅ Created NEW Pending document for manager {reporting_manager_code}")
        else:
            if employee_code not in pending_doc.get("EmployeesCodes", []):
                await db["Pending"].update_one(
                    {"ReportingEmpCode": reporting_manager_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
                print(f"✅ Added employee to Pending list")
        
        # ✅ Delete from Temp_OPE_data
        temp_data_array = temp_doc.get("Data", [])
        
        for i, data_item in enumerate(temp_data_array):
            if formatted_month_range in data_item:
                await db["Temp_OPE_data"].update_one(
                    {"employeeId": employee_code},
                    {"$pull": {"Data": {formatted_month_range: {"$exists": True}}}}
                )
                print(f"✅ Removed from Temp_OPE_data")
                break
        
        # If no more temp data, delete document
        updated_temp = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        if updated_temp and len(updated_temp.get("Data", [])) == 0:
            await db["Temp_OPE_data"].delete_one({"employeeId": employee_code})
            print(f"✅ Deleted empty Temp_OPE_data document")
        
        print(f"\n{'='*60}")
        print(f"✅✅ SUBMISSION COMPLETE ✅✅")
        print(f"   Employee: {employee_code}")
        print(f"   Previous Total: ₹{existing_total}")
        print(f"   New Entries: +₹{new_entries_amount}")
        print(f"   Cumulative Total: ₹{cumulative_total}")
        print(f"   Employee's OPE Limit: ₹{ope_limit}")
        print(f"   Approval Levels: {total_levels}")
        print(f"   OPE Label: {ope_label}")
        print(f"{'='*60}\n")
        
        return {
            "message": "Entries submitted successfully for approval",
            "submitted_count": len(entries_to_submit),
            "month_range": formatted_month_range,
            "reporting_manager": reporting_manager_code,
            "previous_total": existing_total,
            "new_entries_amount": new_entries_amount,
            "total_amount": cumulative_total,
            "ope_limit": ope_limit,  # ✅ Return actual employee limit
            "ope_label": ope_label,
            "total_levels": total_levels,
            "status": "pending_approval"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error submitting final: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))    

@app.post("/api/ope/manager/approve/{employee_code}")
async def approve_employee_entries(
    employee_code: str,
    current_user=Depends(get_current_user)
):
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        print(f"\n{'='*60}")
        print(f"✅ MANAGER APPROVAL REQUEST")
        print(f"Manager: {reporting_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"{'='*60}\n")
        
        # Get manager details
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        manager_name = manager.get("ReportingEmpName", reporting_emp_code)
        
        # Get employee details
        emp = await db["Employee_details"].find_one({"EmpID": employee_code})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        emp_reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
        
        # Get OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No OPE data found for employee")
        
        approved_count = 0
        current_time = datetime.utcnow().isoformat()
        
        data_array = ope_doc.get("Data", [])
        payroll_months_approved = set()
        
        # Approve all pending entries
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    if entry_status != "pending":
                        continue
                    
                    # ✅ APPROVE THIS ENTRY
                    await db["OPE_data"].update_one(
                        {"employeeId": employee_code},
                        {"$set": {
                            f"Data.{i}.{month_range}.{j}.status": "approved",
                            f"Data.{i}.{month_range}.{j}.approved_date": current_time,
                            f"Data.{i}.{month_range}.{j}.approved_by": reporting_emp_code,
                            f"Data.{i}.{month_range}.{j}.approver_name": manager_name,
                            f"Data.{i}.{month_range}.{j}.L1_approved": True,
                            f"Data.{i}.{month_range}.{j}.L1_approver_code": reporting_emp_code,
                            f"Data.{i}.{month_range}.{j}.L1_approver_name": manager_name
                        }}
                    )
                    
                    payroll_months_approved.add(month_range)
                    approved_count += 1
        
        if approved_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found")
        
        # ✅ UPDATE STATUS COLLECTION WITH PROPER ROUTING
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        partner_code = None  # Track partner code for routing
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_approved:
                    total_levels = ps.get("total_levels", 2)
                    submitter_type = ps.get("submitter_type", "Employee")
                    
                    print(f"\n📊 Processing payroll: {ps.get('payroll_month')}")
                    print(f"   Total Levels: {total_levels}")
                    print(f"   Submitter Type: {submitter_type}")
                    
                    # 🔥 CRITICAL FIX: Different routing based on total_levels
                    if total_levels == 2:
                        # ✅ 2-LEVEL: L1 approved → Now pending at L2 (HR)
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L1.status": True,
                                f"approval_status.{i}.L1.approver_code": reporting_emp_code,
                                f"approval_status.{i}.L1.approver_name": manager_name,
                                f"approval_status.{i}.L1.approved_date": current_time,
                                f"approval_status.{i}.overall_status": "pending",
                                f"approval_status.{i}.current_level": "L2"  # ✅ Goes to HR
                            }}
                        )
                        print(f"   ✅ 2-level: L1 approved → L2 (HR) pending")
                        
                    elif total_levels == 3:
                        # 🔥 3-LEVEL: L1 approved → Now pending at L2 (PARTNER)
                        partner_code = ps.get("L2", {}).get("approver_code")
                        
                        if not partner_code:
                            print(f"   ⚠️ WARNING: No Partner code found in Status collection")
                            # Fallback: Get from Employee_details
                            partner_code = emp.get("PartnerEmpCode", "").strip().upper()
                        
                        print(f"   🔥 3-level: L1 approved → L2 (Partner: {partner_code}) pending")
                        
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L1.status": True,
                                f"approval_status.{i}.L1.approver_code": reporting_emp_code,
                                f"approval_status.{i}.L1.approver_name": manager_name,
                                f"approval_status.{i}.L1.approved_date": current_time,
                                f"approval_status.{i}.overall_status": "pending",
                                f"approval_status.{i}.current_level": "L2"  # ✅ Goes to PARTNER (not HR)
                            }}
                        )
        
        # ✅ REMOVE FROM PENDING (Manager's pending list)
        await db["Pending"].update_one(
            {"ReportingEmpCode": emp_reporting_manager_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        print(f"✅ Removed from Manager's Pending")
        
        # ✅ ADD TO APPROVED (Manager's approved list)
        approved_doc = await db["Approved"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not approved_doc:
            await db["Approved"].insert_one({
                "ReportingEmpCode": reporting_emp_code,
                "EmployeesCodes": [employee_code]
            })
            print(f"✅ Created NEW Approved document")
        else:
            if employee_code not in approved_doc.get("EmployeesCodes", []):
                await db["Approved"].update_one(
                    {"ReportingEmpCode": reporting_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
                print(f"✅ Added to Manager's Approved collection")
        
        # 🔥 CRITICAL FIX: Route to Partner's Pending if 3-level
        if partner_code:
            print(f"\n🔥 ROUTING TO PARTNER: {partner_code}")
            
            partner_pending_doc = await db["Pending"].find_one({"ReportingEmpCode": partner_code})
            
            if not partner_pending_doc:
                await db["Pending"].insert_one({
                    "ReportingEmpCode": partner_code,
                    "EmployeesCodes": [employee_code]
                })
                print(f"   ✅ Created NEW Pending document for Partner {partner_code}")
            else:
                if employee_code not in partner_pending_doc.get("EmployeesCodes", []):
                    await db["Pending"].update_one(
                        {"ReportingEmpCode": partner_code},
                        {"$addToSet": {"EmployeesCodes": employee_code}}
                    )
                    print(f"   ✅ Added to Partner's Pending collection")
                else:
                    print(f"   ⚠️ Employee already in Partner's Pending")
        
        print(f"\n✅✅ APPROVAL COMPLETE")
        print(f"   Total approved: {approved_count}")
        print(f"   Next level: {'L2 (Partner)' if partner_code else 'L2 (HR)'}")
        print(f"{'='*60}\n")
        
        return {
            "message": f"Approved {approved_count} entries",
            "approved_count": approved_count,
            "employee_code": employee_code,
            "next_level": "L2",
            "next_approver": partner_code if partner_code else "HR"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"\n❌❌ ERROR:")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/ope/manager/reject/{employee_code}")
async def reject_employee_entries(
    employee_code: str,
    request: Request,
    current_user=Depends(get_current_user)
):
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        body = await request.json()
        rejection_reason = body.get("reason", "No reason provided")
        
        print(f"❌ Rejecting employee {employee_code}")
        
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        manager_name = manager.get("ReportingEmpName", reporting_emp_code)
        
        # Get employee details to determine rejection level
        emp = await db["Employee_details"].find_one({"EmpID": employee_code})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        emp_reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
        emp_partner = emp.get("Partner", "")
        
        # Determine rejection level
        rejection_level = None
        if reporting_emp_code == emp_reporting_manager_code:
            rejection_level = "L1"
        elif manager_name == emp_partner or manager_name in emp_partner:
            rejection_level = "L2"
        else:
            rejection_level = "L3"
        
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No data found")
        
        data_array = ope_doc.get("Data", [])
        rejected_count = 0
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    if entry.get("status", "").lower() == "pending":
                        # Update entry status
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "rejected",
                                f"Data.{i}.{month_range}.{j}.rejected_by": reporting_emp_code,
                                f"Data.{i}.{month_range}.{j}.rejected_date": datetime.utcnow().isoformat(),
                                f"Data.{i}.{month_range}.{j}.rejection_reason": rejection_reason,
                                f"Data.{i}.{month_range}.{j}.rejected_level": rejection_level,  # ✅ NEW
                                f"Data.{i}.{month_range}.{j}.rejector_name": manager_name  # ✅ NEW
                            }}
                        )
                        
                        # Update Status collection
                        status_id = entry.get("status_id")
                        if status_id:
                            await db["Status"].update_one(
                                {"_id": ObjectId(status_id)},
                                {"$set": {
                                    "overall_status": "rejected",
                                    f"{rejection_level}.status": False,
                                    f"{rejection_level}.rejected_by": reporting_emp_code,
                                    f"{rejection_level}.rejected_date": datetime.utcnow().isoformat()
                                }}
                            )
                        
                        rejected_count += 1
        
        if rejected_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found")
        
        # Remove from Pending
        await db["Pending"].update_one(
            {"ReportingEmpCode": emp_reporting_manager_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        
        # Add to Rejected (under CURRENT manager's code)
        rejected_doc = await db["Rejected"].find_one({"ReportingEmpCode": reporting_emp_code})
        
        if not rejected_doc:
            await db["Rejected"].insert_one({
                "ReportingEmpCode": reporting_emp_code,
                "EmployeesCodes": [employee_code]
            })
        else:
            if employee_code not in rejected_doc.get("EmployeesCodes", []):
                await db["Rejected"].update_one(
                    {"ReportingEmpCode": reporting_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
        
        return {
            "message": f"Rejected {rejected_count} entries",
            "rejected_count": rejected_count,
            "rejection_level": rejection_level
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
# ✅ Get list of approved employees for a manager
@app.get("/api/ope/manager/approved-list")
async def get_approved_employees_list(current_user=Depends(get_current_user)):
    """
    Get list of employee codes who have approved entries under this manager
    """
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"📋 Fetching approved list for manager: {reporting_emp_code}")
        
        # Verify user is a manager
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        # Get approved collection
        approved_doc = await db["Approved"].find_one({"ReportingEmpCode": reporting_emp_code})
        
        employee_codes = []
        if approved_doc:
            employee_codes = approved_doc.get("EmployeesCodes", [])
        
        print(f"✅ Found {len(employee_codes)} approved employees")
        
        return {
            "reporting_manager": reporting_emp_code,
            "employee_codes": employee_codes,
            "count": len(employee_codes)
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Get list of rejected employees for a manager
@app.get("/api/ope/manager/rejected-list")
async def get_rejected_employees_list(current_user=Depends(get_current_user)):
    """
    Get list of employee codes who have rejected entries under this manager
    """
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"📋 Fetching rejected list for manager: {reporting_emp_code}")
        
        # Verify user is a manager
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        # Get rejected collection
        rejected_doc = await db["Rejected"].find_one({"ReportingEmpCode": reporting_emp_code})
        
        employee_codes = []
        if rejected_doc:
            employee_codes = rejected_doc.get("EmployeesCodes", [])
        
        print(f"✅ Found {len(employee_codes)} rejected employees")
        
        return {
            "reporting_manager": reporting_emp_code,
            "employee_codes": employee_codes,
            "count": len(employee_codes)
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ✅ Reject a single approved entry
@app.post("/api/ope/manager/reject-single")
async def reject_single_entry(
    request: Request,
    current_user=Depends(get_current_user)
):
    """
    Reject a single approved entry
    """
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        
        body = await request.json()
        entry_id = body.get("entry_id")
        employee_id = body.get("employee_id")
        reason = body.get("reason", "No reason provided")
        
        print(f"❌ Rejecting entry {entry_id} for employee {employee_id}")
        
        # Verify manager
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        manager_name = manager.get("ReportingEmpName", reporting_emp_code)
        
        # Find and update the entry
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_id})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="Employee data not found")
        
        data_array = ope_doc.get("Data", [])
        updated = False
        current_time = datetime.utcnow().isoformat()
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    if str(entry.get("_id")) == entry_id and entry.get("status") == "approved":
                        # ✅ UPDATE ENTRY STATUS
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_id},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "rejected",
                                f"Data.{i}.{month_range}.{j}.rejected_by": reporting_emp_code,
                                f"Data.{i}.{month_range}.{j}.rejector_name": manager_name,  # ✅ KEY FIX
                                f"Data.{i}.{month_range}.{j}.rejected_date": current_time,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": reason
                            }}
                        )
                        
                        # Update Status collection
                        status_id = entry.get("status_id")
                        if status_id:
                            await db["Status"].update_one(
                                {"_id": ObjectId(status_id)},
                                {"$set": {
                                    "overall_status": "rejected",
                                    "L1.status": False,
                                    "L1.rejected_by": reporting_emp_code,
                                    "L1.rejected_date": current_time
                                }}
                            )
                        
                        updated = True
                        break
            if updated:
                break
        
        if not updated:
            raise HTTPException(status_code=404, detail="Entry not found or not approved")
        
        # ✅ CHECK IF ALL ENTRIES ARE REJECTED NOW
        all_rejected = True
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for entry in entries:
                    if str(entry.get("_id")) != entry_id and entry.get("status") == "approved":
                        all_rejected = False
                        break
        
        # ✅ IF ALL REJECTED, MOVE EMPLOYEE
        if all_rejected:
            print(f"🔄 Moving employee from Approved → Rejected")
            
            # Remove from Approved
            await db["Approved"].update_one(
                {"ReportingEmpCode": reporting_emp_code},
                {"$pull": {"EmployeesCodes": employee_id}}
            )
            print(f"✅ Removed from Approved")
            
            # Add to Rejected
            rejected_doc = await db["Rejected"].find_one({"ReportingEmpCode": reporting_emp_code})
            if not rejected_doc:
                await db["Rejected"].insert_one({
                    "ReportingEmpCode": reporting_emp_code,
                    "EmployeesCodes": [employee_id]
                })
                print(f"✅ Created NEW Rejected document")
            else:
                if employee_id not in rejected_doc.get("EmployeesCodes", []):
                    await db["Rejected"].update_one(
                        {"ReportingEmpCode": reporting_emp_code},
                        {"$addToSet": {"EmployeesCodes": employee_id}}
                    )
                    print(f"✅ Added to Rejected collection")
        
        return {"message": "Entry rejected successfully"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

# ✅ Approve a single rejected entry
@app.post("/api/ope/manager/approve-single")
async def approve_single_entry(
    request: Request,
    current_user=Depends(get_current_user)
):
    """
    Approve a single rejected entry
    """
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        
        body = await request.json()
        entry_id = body.get("entry_id")
        employee_id = body.get("employee_id")
        
        print(f"\n{'='*60}")
        print(f"✅ APPROVING REJECTED ENTRY")
        print(f"Manager: {reporting_emp_code}")
        print(f"Employee: {employee_id}")
        print(f"Entry ID: {entry_id}")
        print(f"{'='*60}\n")
        
        # Verify manager
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        manager_name = manager.get("ReportingEmpName", reporting_emp_code)
        
        # Find and update the entry
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_id})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="Employee data not found")
        
        data_array = ope_doc.get("Data", [])
        updated = False
        current_time = datetime.utcnow().isoformat()
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    if str(entry.get("_id")) == entry_id and entry.get("status") == "rejected":
                        # ✅ UPDATE ENTRY STATUS TO APPROVED
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_id},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "approved",
                                f"Data.{i}.{month_range}.{j}.approved_by": reporting_emp_code,
                                f"Data.{i}.{month_range}.{j}.approver_name": manager_name,  # ✅ KEY FIX
                                f"Data.{i}.{month_range}.{j}.approved_date": current_time,
                                # ✅ CLEAR REJECTION DATA
                                f"Data.{i}.{month_range}.{j}.rejected_by": None,
                                f"Data.{i}.{month_range}.{j}.rejector_name": None,
                                f"Data.{i}.{month_range}.{j}.rejected_date": None,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": None
                            }}
                        )
                        
                        # Update Status collection
                        status_id = entry.get("status_id")
                        if status_id:
                            await db["Status"].update_one(
                                {"_id": ObjectId(status_id)},
                                {"$set": {
                                    "overall_status": "approved",
                                    "L1.status": True,
                                    "L1.approver_code": reporting_emp_code,
                                    "L1.approver_name": manager_name,
                                    "L1.approved_date": current_time,
                                    "L1.rejected_by": None,
                                    "L1.rejected_date": None
                                }}
                            )
                        
                        updated = True
                        print(f"✅ Entry updated to approved")
                        break
            if updated:
                break
        
        if not updated:
            raise HTTPException(status_code=404, detail="Entry not found or not rejected")
        
        # ✅ CHECK IF ALL ENTRIES ARE NOW APPROVED
        all_approved = True
        any_rejected = False
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for entry in entries:
                    entry_status = entry.get("status", "").lower()
                    if str(entry.get("_id")) != entry_id:
                        if entry_status == "rejected":
                            any_rejected = True
                            all_approved = False
                            break
                        elif entry_status != "approved":
                            all_approved = False
        
        print(f"📊 Status check:")
        print(f"   All approved: {all_approved}")
        print(f"   Any rejected: {any_rejected}")
        
        # ✅ IF NO MORE REJECTED ENTRIES, MOVE FROM REJECTED TO APPROVED
        if not any_rejected:
            print(f"🔄 Moving employee from Rejected → Approved")
            
            # ✅ REMOVE FROM REJECTED COLLECTION
            await db["Rejected"].update_one(
                {"ReportingEmpCode": reporting_emp_code},
                {"$pull": {"EmployeesCodes": employee_id}}
            )
            print(f"✅ Removed from Rejected collection")
            
            # ✅ ADD TO APPROVED COLLECTION
            approved_doc = await db["Approved"].find_one({"ReportingEmpCode": reporting_emp_code})
            if not approved_doc:
                await db["Approved"].insert_one({
                    "ReportingEmpCode": reporting_emp_code,
                    "EmployeesCodes": [employee_id]
                })
                print(f"✅ Created NEW Approved document")
            else:
                if employee_id not in approved_doc.get("EmployeesCodes", []):
                    await db["Approved"].update_one(
                        {"ReportingEmpCode": reporting_emp_code},
                        {"$addToSet": {"EmployeesCodes": employee_id}}
                    )
                    print(f"✅ Added to Approved collection")
                else:
                    print(f"⚠️ Employee already in Approved collection")
        else:
            print(f"⚠️ Employee still has rejected entries, not moving collections")
        
        print(f"{'='*60}\n")
        
        return {"message": "Entry approved successfully"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
@app.get("/api/ope/status/{employee_code}")
async def get_employee_status(employee_code: str, current_user=Depends(get_current_user)):
    """
    Get approval status for all payroll months of an employee
    """
    try:
        employee_code = employee_code.strip().upper()
        current_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"📊 Fetching status for: {employee_code}")
        
        if current_emp_code != employee_code:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # ✅ Get Status document for this employee
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if not status_doc:
            return {"status_entries": []}
        
        approval_status = status_doc.get("approval_status", [])
        
        print(f"✅ Found {len(approval_status)} payroll months")
        
        status_entries = []
        
        for ps in approval_status:
            entry = {
                "employeeId": employee_code,
                "employeeName": status_doc.get("employeeName", ""),
                "payroll_month": ps.get("payroll_month"),
                "ope_label": ps.get("ope_label"),
                "total_levels": ps.get("total_levels"),
                "limit": ps.get("limit"),
                "total_amount": ps.get("total_amount"),
                "L1": ps.get("L1", {}),
                "L2": ps.get("L2", {}),
                "current_level": ps.get("current_level"),
                "overall_status": ps.get("overall_status"),
                "submission_date": ps.get("submission_date")
            }
            
            # ✅ Add L3 only if it exists
            if "L3" in ps:
                entry["L3"] = ps.get("L3", {})
            
            status_entries.append(entry)
        
        return {"status_entries": status_entries}
        
    except Exception as e:
        print(f"❌ Error fetching status: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

# HR API

@app.post("/api/ope/hr/approve/{employee_code}")
async def hr_approve_employee(
    employee_code: str,
    current_user=Depends(get_current_user)
):
    """
    HR approval - approves ALL pending HR entries for an employee
    """
    try:
        hr_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        print(f"\n{'='*60}")
        print(f"✅ HR APPROVAL REQUEST")
        print(f"HR: {hr_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"{'='*60}\n")
        
        # ✅ VERIFY USER IS HR
        if hr_emp_code != "JHS729":
            raise HTTPException(status_code=403, detail="Only HR can perform this action")
        
        # Get OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No OPE data found")
        
        approved_count = 0
        current_time = datetime.utcnow().isoformat()
        
        data_array = ope_doc.get("Data", [])
        payroll_months_approved = set()
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    # ✅ HR approves entries that are "approved" (approved by L1/L2 but not HR yet)
                    # OR entries that are "rejected" (re-approving rejected entries)
                    if entry_status in ["approved", "rejected"]:
                        # Mark as HR approved
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "approved",
                                f"Data.{i}.{month_range}.{j}.hr_approved": True,
                                f"Data.{i}.{month_range}.{j}.hr_approved_by": hr_emp_code,
                                f"Data.{i}.{month_range}.{j}.hr_approved_date": current_time,
                                f"Data.{i}.{month_range}.{j}.approved_by": hr_emp_code,
                                f"Data.{i}.{month_range}.{j}.approver_name": "HR",
                                f"Data.{i}.{month_range}.{j}.approved_date": current_time,
                                # Clear rejection data if re-approving
                                f"Data.{i}.{month_range}.{j}.rejected_by": None,
                                f"Data.{i}.{month_range}.{j}.rejector_name": None,
                                f"Data.{i}.{month_range}.{j}.rejected_date": None,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": None,
                                f"Data.{i}.{month_range}.{j}.rejected_level": None
                            }}
                        )
                        
                        payroll_months_approved.add(month_range)
                        approved_count += 1
        
        if approved_count == 0:
            raise HTTPException(status_code=404, detail="No entries found for HR approval")
        
        # ✅ UPDATE STATUS COLLECTION
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_approved:
                    total_levels = ps.get("total_levels", 2)
                    
                    if total_levels == 2:
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L2.status": True,
                                f"approval_status.{i}.L2.approver_code": hr_emp_code,
                                f"approval_status.{i}.L2.approver_name": "HR",
                                f"approval_status.{i}.L2.approved_date": current_time,
                                f"approval_status.{i}.overall_status": "approved",
                                f"approval_status.{i}.current_level": "Completed"
                            }}
                        )
                    elif total_levels == 3:
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L3.status": True,
                                f"approval_status.{i}.L3.approver_code": hr_emp_code,
                                f"approval_status.{i}.L3.approver_name": "HR",
                                f"approval_status.{i}.L3.approved_date": current_time,
                                f"approval_status.{i}.overall_status": "approved",
                                f"approval_status.{i}.current_level": "Completed"
                            }}
                        )
        
        # ✅ UPDATE COLLECTIONS
        # Add to HR_Approved
        hr_approved_doc = await db["HR_Approved"].find_one({"HR_Code": hr_emp_code})
        
        if not hr_approved_doc:
            await db["HR_Approved"].insert_one({
                "HR_Code": hr_emp_code,
                "EmployeesCodes": [employee_code]
            })
        else:
            if employee_code not in hr_approved_doc.get("EmployeesCodes", []):
                await db["HR_Approved"].update_one(
                    {"HR_Code": hr_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
        
        # Remove from HR_Rejected
        await db["HR_Rejected"].update_one(
            {"HR_Code": hr_emp_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        
        print(f"✅ HR approved {approved_count} entries")
        
        return {
            "message": f"HR approved {approved_count} entries",
            "approved_count": approved_count
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        

@app.post("/api/ope/hr/reject/{employee_code}")
async def hr_reject_employee(
    employee_code: str,
    request: Request,
    current_user=Depends(get_current_user)
):
    """
    HR rejection - rejects ALL pending HR entries for an employee
    """
    try:
        hr_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        body = await request.json()
        rejection_reason = body.get("reason", "No reason provided")
        
        print(f"\n{'='*60}")
        print(f"❌ HR REJECTION REQUEST")
        print(f"HR: {hr_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"{'='*60}\n")
        
        # ✅ VERIFY USER IS HR
        if hr_emp_code != "JHS729":
            raise HTTPException(status_code=403, detail="Only HR can perform this action")
        
        # Get OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No OPE data found")
        
        rejected_count = 0
        current_time = datetime.utcnow().isoformat()
        
        data_array = ope_doc.get("Data", [])
        payroll_months_rejected = set()
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    # ✅ HR can reject "approved" entries (those pending HR approval)
                    if entry_status == "approved":
                        # Mark as rejected by HR
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "rejected",
                                f"Data.{i}.{month_range}.{j}.rejected_by": hr_emp_code,
                                f"Data.{i}.{month_range}.{j}.rejector_name": "HR",
                                f"Data.{i}.{month_range}.{j}.rejected_date": current_time,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": rejection_reason,
                                f"Data.{i}.{month_range}.{j}.rejected_level": "L2",  # HR level
                                # Clear HR approval data
                                f"Data.{i}.{month_range}.{j}.hr_approved": False,
                                f"Data.{i}.{month_range}.{j}.hr_approved_by": None,
                                f"Data.{i}.{month_range}.{j}.hr_approved_date": None
                            }}
                        )
                        
                        payroll_months_rejected.add(month_range)
                        rejected_count += 1
        
        if rejected_count == 0:
            raise HTTPException(status_code=404, detail="No entries found for HR rejection")
        
        # ✅ UPDATE STATUS COLLECTION
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_rejected:
                    total_levels = ps.get("total_levels", 2)
                    
                    if total_levels == 2:
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L2.status": False,
                                f"approval_status.{i}.L2.rejected_by": hr_emp_code,
                                f"approval_status.{i}.L2.rejected_date": current_time,
                                f"approval_status.{i}.overall_status": "rejected",
                                f"approval_status.{i}.rejection_reason": rejection_reason
                            }}
                        )
                    elif total_levels == 3:
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L3.status": False,
                                f"approval_status.{i}.L3.rejected_by": hr_emp_code,
                                f"approval_status.{i}.L3.rejected_date": current_time,
                                f"approval_status.{i}.overall_status": "rejected",
                                f"approval_status.{i}.rejection_reason": rejection_reason
                            }}
                        )
        
        # ✅ UPDATE COLLECTIONS
        # Add to HR_Rejected
        hr_rejected_doc = await db["HR_Rejected"].find_one({"HR_Code": hr_emp_code})
        
        if not hr_rejected_doc:
            await db["HR_Rejected"].insert_one({
                "HR_Code": hr_emp_code,
                "EmployeesCodes": [employee_code]
            })
        else:
            if employee_code not in hr_rejected_doc.get("EmployeesCodes", []):
                await db["HR_Rejected"].update_one(
                    {"HR_Code": hr_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
        
        # Remove from HR_Approved
        await db["HR_Approved"].update_one(
            {"HR_Code": hr_emp_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        
        print(f"✅ HR rejected {rejected_count} entries")
        
        return {
            "message": f"HR rejected {rejected_count} entries",
            "rejected_count": rejected_count
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/api/ope/hr/is-hr")
async def check_if_hr(current_user=Depends(get_current_user)):
    """
    Check if current user is HR
    """
    try:
        emp_code = current_user["employee_code"].strip().upper()
        is_hr = (emp_code == "JHS729")
        
        return {
            "employee_code": emp_code,
            "is_hr": is_hr
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/ope/hr/approved-employees")
async def get_hr_approved_employees(current_user=Depends(get_current_user)):
    """
    Get list of employees with entries approved by HR
    """
    try:
        hr_emp_code = current_user["employee_code"].strip().upper()
        
        if hr_emp_code != "JHS729":
            raise HTTPException(status_code=403, detail="Only HR can access this")
        
        print(f"📋 Fetching HR approved employees")
        
        # ✅ Get from HR_Approved collection
        hr_approved_doc = await db["HR_Approved"].find_one({"HR_Code": hr_emp_code})
        
        employee_codes = []
        if hr_approved_doc:
            employee_codes = hr_approved_doc.get("EmployeesCodes", [])
        
        print(f"✅ Found {len(employee_codes)} HR approved employees")
        
        return {
            "employee_codes": employee_codes,
            "count": len(employee_codes)
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ope/hr/rejected-employees")
async def get_hr_rejected_employees(current_user=Depends(get_current_user)):
    """
    Get list of employees with entries rejected by HR
    """
    try:
        hr_emp_code = current_user["employee_code"].strip().upper()
        
        if hr_emp_code != "JHS729":
            raise HTTPException(status_code=403, detail="Only HR can access this")
        
        print(f"📋 Fetching HR rejected employees")
        
        # ✅ Get from HR_Rejected collection
        hr_rejected_doc = await db["HR_Rejected"].find_one({"HR_Code": hr_emp_code})
        
        employee_codes = []
        if hr_rejected_doc:
            employee_codes = hr_rejected_doc.get("EmployeesCodes", [])
        
        print(f"✅ Found {len(employee_codes)} HR rejected employees")
        
        return {
            "employee_codes": employee_codes,
            "count": len(employee_codes)
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
@app.get("/api/check-partner/{employee_code}")
async def check_if_partner(employee_code: str, current_user=Depends(get_current_user)):
    """
    Check if the logged-in employee is a Partner
    """
    try:
        emp_code = employee_code.strip().upper()
        
        print(f"🔍 Checking if {emp_code} is a Partner...")
        
        # Verify user can only check their own role
        if current_user["employee_code"].upper() != emp_code:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check in Partner collection
        partner = await db["Partner"].find_one({"PartnerEmpCode": emp_code})
        
        is_partner = partner is not None
        
        if is_partner:
            print(f"✅ {emp_code} IS a Partner")
        else:
            print(f"❌ {emp_code} is NOT a Partner")
        
        return {
            "employee_code": emp_code,
            "isPartner": is_partner,
            "partner_name": partner.get("Partner_Name") if partner else None
        }
        
    except Exception as e:
        print(f"❌ Error checking partner role: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    

# ✅ FIXED VERSION - Replace your existing @app.get("/api/ope/partner/pending") with this:
# ✅ CORRECTED VERSION - Partner ko L1-approved entries dikhani chahiye!

@app.get("/api/ope/partner/pending")
async def get_partner_pending_employees(current_user=Depends(get_current_user)):
    """
    Get employees pending Partner approval
    Shows entries where:
    - total_levels = 3
    - L1.status = True (Manager approved)
    - current_level = "L2" (Pending at Partner)
    - overall_status = "pending"
    """
    try:
        partner_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"\n{'='*60}")
        print(f"🔍 PARTNER PENDING REQUEST FROM: {partner_emp_code}")
        print(f"{'='*60}")
        
        # ✅ Verify user is a partner
        partner = await db["Partner"].find_one({"PartnerEmpCode": partner_emp_code})
        if not partner:
            raise HTTPException(status_code=403, detail="You are not a Partner")
        
        partner_name = partner.get("Partner_Name", partner_emp_code)
        
        # 🔥 METHOD 1: Use Pending collection (Fast)
        pending_doc = await db["Pending"].find_one({"ReportingEmpCode": partner_emp_code})
        
        if not pending_doc:
            print(f"📭 No pending document found for Partner {partner_emp_code}")
            return {"employees": [], "count": 0}
        
        employee_codes = pending_doc.get("EmployeesCodes", [])
        print(f"📊 Found {len(employee_codes)} employees in Pending collection")
        
        pending_employees = []
        
        # ✅ For each employee, get their OPE data
        for emp_code in employee_codes:
            print(f"\n✅ Processing Employee: {emp_code}")
            
            # Get Status document to verify 3-level and L1 approval
            status_doc = await db["Status"].find_one({"employeeId": emp_code})
            
            if not status_doc:
                print(f"   ⚠️ No Status document found - skipping")
                continue
            
            # Get OPE data
            ope_doc = await db["OPE_data"].find_one({"employeeId": emp_code})
            
            if not ope_doc:
                print(f"   ⚠️ No OPE data found - skipping")
                continue
            
            approval_statuses = status_doc.get("approval_status", [])
            
            for approval_status in approval_statuses:
                # ✅ STRICT FILTERING: Only 3-level, L1-approved, L2-pending
                if (
                    approval_status.get("total_levels") == 3 and
                    approval_status.get("current_level") == "L2" and
                    approval_status.get("L1", {}).get("status") == True and
                    approval_status.get("L2", {}).get("approver_code") == partner_emp_code and
                    approval_status.get("overall_status") == "pending"
                ):
                    payroll_month = approval_status.get("payroll_month")
                    total_amount = approval_status.get("total_amount", 0)
                    limit = approval_status.get("limit", 0)
                    
                    print(f"   ✅ MATCH FOUND:")
                    print(f"      Month: {payroll_month}")
                    print(f"      Amount: ₹{total_amount} | Limit: ₹{limit}")
                    print(f"      L1 Approver: {approval_status.get('L1', {}).get('approver_name')}")
                    
                    # ✅ Fetch entries from OPE_data
                    entries = []
                    data_array = ope_doc.get("Data", [])
                    
                    for data_item in data_array:
                        if payroll_month in data_item:
                            month_entries = data_item[payroll_month]
                            
                            # ✅ CRITICAL: Show "approved" entries (L1 approved, waiting for Partner L2)
                            for entry in month_entries:
                                entry_status = str(entry.get("status", "")).lower().strip()
                                
                                # Partner sees entries that are "approved" by Manager (L1)
                                if entry_status == "approved":
                                    entries.append({
                                        "_id": str(entry.get("_id", "")),
                                        "date": entry.get("date", ""),
                                        "client": entry.get("client", ""),
                                        "project_id": entry.get("project_id", ""),
                                        "project_name": entry.get("project_name", ""),
                                        "project_type": entry.get("project_type", ""),
                                        "location_from": entry.get("location_from", ""),
                                        "location_to": entry.get("location_to", ""),
                                        "travel_mode": entry.get("travel_mode", ""),
                                        "amount": entry.get("amount", 0),
                                        "remarks": entry.get("remarks", ""),
                                        "ticket_pdf": entry.get("ticket_pdf", ""),
                                        "status": "approved",  # L1 approved
                                        "month_range": payroll_month,
                                        "L1_approver": approval_status.get("L1", {}).get("approver_name"),
                                        "L1_approved_date": approval_status.get("L1", {}).get("approved_date")
                                    })
                            
                            print(f"      📦 Collected {len(entries)} entries")
                            break
                    
                    # ✅ ONLY add if entries exist
                    if entries:
                        pending_employees.append({
                            "employeeId": emp_code,
                            "employeeName": ope_doc.get("employeeName", ""),
                            "designation": ope_doc.get("designation", ""),
                            "department": ope_doc.get("department", ""),
                            "reportingManager": ope_doc.get("reportingManager", ""),
                            "payroll_month": payroll_month,
                            "total_amount": total_amount,
                            "limit": limit,
                            "ope_label": approval_status.get("ope_label", ""),
                            "total_levels": 3,
                            "current_level": "L2",
                            "L1_approver": approval_status.get("L1", {}).get("approver_name", ""),
                            "L1_approved_date": approval_status.get("L1", {}).get("approved_date", ""),
                            "submission_date": approval_status.get("submission_date", ""),
                            "entries": entries,
                            "entry_count": len(entries)
                        })
                        print(f"      ✅ Added employee with {len(entries)} entries")
        
        print(f"\n{'='*60}")
        print(f"✅ Returning {len(pending_employees)} employees for Partner {partner_emp_code}")
        print(f"{'='*60}\n")
        
        return {
            "employees": pending_employees,
            "count": len(pending_employees),
            "partner_code": partner_emp_code,
            "partner_name": partner_name
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error fetching partner pending: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/ope/partner/approve/{employee_code}")
async def partner_approve_employee(
    employee_code: str,
    current_user=Depends(get_current_user)
):
    """
    Partner approval for 3-level employee OPE
    After approval, routes to HR (L3)
    """
    try:
        partner_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        print(f"\n{'='*60}")
        print(f"✅ PARTNER APPROVAL REQUEST")
        print(f"Partner: {partner_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"{'='*60}\n")
        
        # Verify user is a partner
        partner = await db["Partner"].find_one({"PartnerEmpCode": partner_emp_code})
        if not partner:
            raise HTTPException(status_code=403, detail="You are not a Partner")
        
        partner_name = partner.get("Partner_Name", partner_emp_code)
        
        # Get OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No OPE data found")
        
        approved_count = 0
        current_time = datetime.utcnow().isoformat()
        
        data_array = ope_doc.get("Data", [])
        payroll_months_approved = set()
        
        # ✅ Approve all "approved" entries (L1 approved, waiting for Partner L2)
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    # Approve entries with status "approved" (waiting for Partner)
                    if entry_status == "approved":
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "approved",  # Still approved
                                f"Data.{i}.{month_range}.{j}.partner_approved": True,
                                f"Data.{i}.{month_range}.{j}.partner_approved_by": partner_emp_code,
                                f"Data.{i}.{month_range}.{j}.partner_approved_date": current_time,
                                f"Data.{i}.{month_range}.{j}.L2_approved": True,
                                f"Data.{i}.{month_range}.{j}.L2_approver_code": partner_emp_code,
                                f"Data.{i}.{month_range}.{j}.L2_approver_name": partner_name
                            }}
                        )
                        
                        payroll_months_approved.add(month_range)
                        approved_count += 1
                        print(f"   ✅ Approved entry: {month_range} | Date: {entry.get('date')} | Amount: ₹{entry.get('amount')}")
        
        if approved_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found for approval")
        
        # ✅ UPDATE STATUS COLLECTION
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_approved:
                    total_levels = ps.get("total_levels", 3)
                    
                    print(f"\n📊 Updating Status for: {ps.get('payroll_month')}")
                    print(f"   Total Levels: {total_levels}")
                    
                    # 🔥 L2 (Partner) approved, now move to L3 (HR)
                    await db["Status"].update_one(
                        {"employeeId": employee_code},
                        {"$set": {
                            f"approval_status.{i}.L2.status": True,
                            f"approval_status.{i}.L2.approver_code": partner_emp_code,
                            f"approval_status.{i}.L2.approver_name": partner_name,
                            f"approval_status.{i}.L2.approved_date": current_time,
                            f"approval_status.{i}.current_level": "L3",  # ✅ Now pending at HR
                            f"approval_status.{i}.overall_status": "pending"
                        }}
                    )
                    print(f"   ✅ L2 approved → L3 (HR) pending")
        
        # ✅ REMOVE FROM PENDING (Partner's pending)
        await db["Pending"].update_one(
            {"ReportingEmpCode": partner_emp_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        print(f"✅ Removed from Partner's Pending")
        
        # ✅ ADD TO APPROVED (Partner's approved)
        partner_approved_doc = await db["Partner_Approved"].find_one(
            {"PartnerEmpCode": partner_emp_code}
        )
        
        if not partner_approved_doc:
            await db["Partner_Approved"].insert_one({
                "PartnerEmpCode": partner_emp_code,
                "EmployeesCodes": [employee_code]
            })
            print(f"✅ Created NEW Partner_Approved document")
        else:
            if employee_code not in partner_approved_doc.get("EmployeesCodes", []):
                await db["Partner_Approved"].update_one(
                    {"PartnerEmpCode": partner_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
                print(f"✅ Added to Partner's Approved collection")
        
        # 🔥 NO NEED TO ADD TO HR PENDING - HR endpoint filters by L2.status = True
        print(f"\n✅ Data will appear in HR pending (filters by current_level=L3)")
        
        print(f"\n{'='*60}")
        print(f"✅ Partner approved {approved_count} entries for {employee_code}")
        print(f"   Next Level: L3 (HR)")
        print(f"{'='*60}\n")
        
        return {
            "message": f"Successfully approved {approved_count} entries",
            "approved_count": approved_count,
            "next_level": "L3",
            "next_approver": "HR"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error in partner approve: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/api/ope/partner/reject/{employee_code}")
async def partner_reject_employee(
    employee_code: str,
    request: Request,
    current_user=Depends(get_current_user)
):
    """
    Partner rejection for an employee's OPE
    """
    try:
        partner_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        body = await request.json()
        rejection_reason = body.get("reason", "No reason provided")
        
        print(f"\n{'='*60}")
        print(f"❌ PARTNER REJECTION")
        print(f"Partner: {partner_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"{'='*60}\n")
        
        # Verify user is a partner
        partner = await db["Partner"].find_one({"PartnerEmpCode": partner_emp_code})
        if not partner:
            raise HTTPException(status_code=403, detail="You are not a Partner")
        
        partner_name = partner.get("Partner_Name", partner_emp_code)
        
        # Get OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No OPE data found")
        
        rejected_count = 0
        current_time = datetime.utcnow().isoformat()
        
        data_array = ope_doc.get("Data", [])
        payroll_months_rejected = set()
        
        # ✅ REJECT ALL PENDING ENTRIES
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    # Reject entries with status "approved" (waiting for Partner)
                    if entry_status == "approved":
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "rejected",
                                f"Data.{i}.{month_range}.{j}.rejected_by": partner_emp_code,
                                f"Data.{i}.{month_range}.{j}.rejector_name": partner_name,
                                f"Data.{i}.{month_range}.{j}.rejected_date": current_time,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": rejection_reason,
                                f"Data.{i}.{month_range}.{j}.rejected_level": "L2"
                            }}
                        )
                        
                        payroll_months_rejected.add(month_range)
                        rejected_count += 1
        
        if rejected_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found")
        
        # ✅ UPDATE STATUS COLLECTION
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_rejected:
                    submitter_type = ps.get("submitter_type", "Employee")
                    
                    if submitter_type == "Reporting_Manager":
                        # Manager OPE rejected at L1 (Partner)
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L1.status": False,
                                f"approval_status.{i}.L1.rejected_by": partner_emp_code,
                                f"approval_status.{i}.L1.rejected_date": current_time,
                                f"approval_status.{i}.overall_status": "rejected",
                                f"approval_status.{i}.rejection_reason": rejection_reason
                            }}
                        )
                    else:
                        # Employee OPE rejected at L2 (Partner)
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L2.status": False,
                                f"approval_status.{i}.L2.rejected_by": partner_emp_code,
                                f"approval_status.{i}.L2.rejected_date": current_time,
                                f"approval_status.{i}.overall_status": "rejected",
                                f"approval_status.{i}.rejection_reason": rejection_reason
                            }}
                        )
        
        # ✅ REMOVE FROM PENDING
        await db["Pending"].update_one(
            {"ReportingEmpCode": partner_emp_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        
        # ✅ ADD TO REJECTED
        partner_rejected_doc = await db["Partner_Rejected"].find_one(
            {"PartnerEmpCode": partner_emp_code}
        )
        
        if not partner_rejected_doc:
            await db["Partner_Rejected"].insert_one({
                "PartnerEmpCode": partner_emp_code,
                "EmployeesCodes": [employee_code]
            })
        else:
            if employee_code not in partner_rejected_doc.get("EmployeesCodes", []):
                await db["Partner_Rejected"].update_one(
                    {"PartnerEmpCode": partner_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
        
        print(f"✅ Partner rejected {rejected_count} entries")
        
        return {
            "message": f"Partner rejected {rejected_count} entries",
            "rejected_count": rejected_count
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/ope/partner/approved-list")
async def get_partner_approved_list(current_user=Depends(get_current_user)):
    """
    Get list of employees approved by Partner
    """
    try:
        partner_emp_code = current_user["employee_code"].strip().upper()
        
        partner = await db["Partner"].find_one({"PartnerEmpCode": partner_emp_code})
        if not partner:
            raise HTTPException(status_code=403, detail="You are not a Partner")
        
        partner_approved_doc = await db["Partner_Approved"].find_one(
            {"PartnerEmpCode": partner_emp_code}
        )
        
        employee_codes = []
        if partner_approved_doc:
            employee_codes = partner_approved_doc.get("EmployeesCodes", [])
        
        return {
            "partner_code": partner_emp_code,
            "employee_codes": employee_codes,
            "count": len(employee_codes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/check-user-role/{employee_code}")
async def check_user_role(employee_code: str, current_user=Depends(get_current_user)):
    """
    Unified endpoint to check user role
    Priority: HR > Partner > Manager > Employee
    Returns ONLY ONE primary role (highest priority)
    """
    try:
        emp_code = employee_code.strip().upper()
        
        # Verify user can only check their own role
        if current_user["employee_code"].upper() != emp_code:
            raise HTTPException(status_code=403, detail="Access denied")
        
        print(f"🔍 Checking unified role for: {emp_code}")
        
        # ✅ PRIORITY-BASED ROLE DETECTION
        role_name = "Employee"  # Default
        is_hr = False
        is_partner = False
        is_manager = False
        is_employee = False
        has_approval_permissions = False
        additional_info = {}
        
        # ✅ PRIORITY 1: Check if HR (highest priority)
        if emp_code == "JHS729":
            is_hr = True
            role_name = "HR"
            has_approval_permissions = True
            print(f"👔 {emp_code} is HR")
            
        # ✅ PRIORITY 2: Check if Partner (only if not HR)
        elif await db["Partner"].find_one({"PartnerEmpCode": emp_code}):
            partner = await db["Partner"].find_one({"PartnerEmpCode": emp_code})
            is_partner = True
            role_name = "Partner"
            has_approval_permissions = True
            additional_info["partner_name"] = partner.get("Partner_Name")
            print(f"👔 {emp_code} is a Partner (NOT checking manager)")
            
        # ✅ PRIORITY 3: Check if Reporting Manager (only if not HR or Partner)
        elif await db["Reporting_managers"].find_one({"ReportingEmpCode": emp_code}):
            manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": emp_code})
            is_manager = True
            role_name = "Reporting Manager"
            has_approval_permissions = True
            additional_info["manager_name"] = manager.get("ReportingEmpName")
            additional_info["email"] = manager.get("Email ID")
            print(f"👔 {emp_code} is a Reporting Manager")
            
        # ✅ PRIORITY 4: Regular Employee (if none of the above)
        else:
            is_employee = True
            role_name = "Employee"
            has_approval_permissions = False
            print(f"👤 {emp_code} is a regular Employee")
        
        return {
            "employee_code": emp_code,
            "role": role_name,  # Primary role ONLY
            "is_hr": is_hr,
            "is_partner": is_partner,
            "is_manager": is_manager,
            "is_employee": is_employee,
            "has_approval_permissions": has_approval_permissions,
            "additional_info": additional_info
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error checking user role: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ope/partner/rejected-list")
async def get_partner_rejected_list(current_user=Depends(get_current_user)):
    """
    Get list of employees rejected by Partner
    """
    try:
        partner_emp_code = current_user["employee_code"].strip().upper()
        
        partner = await db["Partner"].find_one({"PartnerEmpCode": partner_emp_code})
        if not partner:
            raise HTTPException(status_code=403, detail="You are not a Partner")
        
        partner_rejected_doc = await db["Partner_Rejected"].find_one(
            {"PartnerEmpCode": partner_emp_code}
        )
        
        employee_codes = []
        if partner_rejected_doc:
            employee_codes = partner_rejected_doc.get("EmployeesCodes", [])
        
        return {
            "partner_code": partner_emp_code,
            "employee_codes": employee_codes,
            "count": len(employee_codes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/debug/check-partner-data/{employee_code}")
async def debug_check_partner_data(employee_code: str):
    """Debug: Check what data exists for partner approval"""
    try:
        partner_code = employee_code.strip().upper()
        
        # 1. Check Status collection
        status_docs = await db["Status"].find({}).to_list(length=None)
        
        partner_matches = []
        for doc in status_docs:
            emp_id = doc.get("employeeId")
            approval_statuses = doc.get("approval_status", [])
            
            for ps in approval_statuses:
                if ps.get("total_levels") == 3:
                    l2_code = ps.get("L2", {}).get("approver_code", "")
                    if l2_code == partner_code:
                        partner_matches.append({
                            "employeeId": emp_id,
                            "payroll_month": ps.get("payroll_month"),
                            "total_levels": ps.get("total_levels"),
                            "current_level": ps.get("current_level"),
                            "L1_status": ps.get("L1", {}).get("status"),
                            "L2_approver_code": l2_code,
                            "overall_status": ps.get("overall_status")
                        })
        
        return {
            "partner_code": partner_code,
            "total_status_docs": len(status_docs),
            "partner_matches": partner_matches,
            "match_count": len(partner_matches)
        }
        
    except Exception as e:
        return {"error": str(e)}
    
# ============================================
# PARTNER APPROVE ENDPOINT - Add to main.py
# ============================================

@app.post("/api/ope/partner/approve/{employee_code}")
async def partner_approve_employee(
    employee_code: str,
    current_user=Depends(get_current_user)
):
    """Partner approval for employee OPE"""
    try:
        partner_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        print(f"\n{'='*60}")
        print(f"✅ PARTNER APPROVAL REQUEST")
        print(f"Partner: {partner_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"{'='*60}\n")
        
        # Verify user is a partner
        partner = await db["Partner"].find_one({"PartnerEmpCode": partner_emp_code})
        if not partner:
            raise HTTPException(status_code=403, detail="You are not a Partner")
        
        partner_name = partner.get("Partner_Name", partner_emp_code)
        
        # Get OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No OPE data found")
        
        approved_count = 0
        current_time = datetime.utcnow().isoformat()
        
        data_array = ope_doc.get("Data", [])
        payroll_months_approved = set()
        
        # ✅ Approve all "approved" entries (L1 approved, now approving at L2)
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    # Approve entries with status "approved" (waiting for Partner L2)
                    if entry_status == "approved":
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.partner_approved": True,
                                f"Data.{i}.{month_range}.{j}.partner_approved_by": partner_emp_code,
                                f"Data.{i}.{month_range}.{j}.partner_approved_date": current_time,
                                f"Data.{i}.{month_range}.{j}.partner_name": partner_name
                            }}
                        )
                        
                        payroll_months_approved.add(month_range)
                        approved_count += 1
                        print(f"   ✅ Approved entry: {month_range} | Date: {entry.get('date')} | Amount: ₹{entry.get('amount')}")
        
        if approved_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found for approval")
        
        # ✅ Update Status collection
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_approved:
                    # L2 (Partner) approved, now move to L3 (HR)
                    await db["Status"].update_one(
                        {"employeeId": employee_code},
                        {"$set": {
                            f"approval_status.{i}.L2.status": True,
                            f"approval_status.{i}.L2.approver_code": partner_emp_code,
                            f"approval_status.{i}.L2.approver_name": partner_name,
                            f"approval_status.{i}.L2.approved_date": current_time,
                            f"approval_status.{i}.current_level": "L3"
                        }}
                    )
                    print(f"   📊 Updated Status: {ps.get('payroll_month')} → L3 (HR pending)")
        
        # ✅ Add to Partner_Approved collection
        partner_approved_doc = await db["Partner_Approved"].find_one(
            {"PartnerEmpCode": partner_emp_code}
        )
        
        if not partner_approved_doc:
            await db["Partner_Approved"].insert_one({
                "PartnerEmpCode": partner_emp_code,
                "EmployeesCodes": [employee_code]
            })
            print(f"   📝 Created new Partner_Approved document")
        else:
            if employee_code not in partner_approved_doc.get("EmployeesCodes", []):
                await db["Partner_Approved"].update_one(
                    {"PartnerEmpCode": partner_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
                print(f"   📝 Added to Partner_Approved collection")
        
        print(f"\n{'='*60}")
        print(f"✅ Partner approved {approved_count} entries for {employee_code}")
        print(f"{'='*60}\n")
        
        return {
            "message": f"Successfully approved {approved_count} entries",
            "approved_count": approved_count
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error in partner approve: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# PARTNER REJECT ENDPOINT - Add to main.py
# ============================================

@app.post("/api/ope/partner/reject/{employee_code}")
async def partner_reject_employee(
    employee_code: str,
    request: Request,
    current_user=Depends(get_current_user)
):
    """Partner rejection for employee OPE"""
    try:
        partner_emp_code = current_user["employee_code"].strip().upper()
        employee_code = employee_code.strip().upper()
        
        body = await request.json()
        rejection_reason = body.get("reason", "No reason provided")
        
        print(f"\n{'='*60}")
        print(f"❌ PARTNER REJECTION REQUEST")
        print(f"Partner: {partner_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"Reason: {rejection_reason}")
        print(f"{'='*60}\n")
        
        # Verify user is a partner
        partner = await db["Partner"].find_one({"PartnerEmpCode": partner_emp_code})
        if not partner:
            raise HTTPException(status_code=403, detail="You are not a Partner")
        
        partner_name = partner.get("Partner_Name", partner_emp_code)
        
        # Get OPE data
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        if not ope_doc:
            raise HTTPException(status_code=404, detail="No OPE data found")
        
        rejected_count = 0
        current_time = datetime.utcnow().isoformat()
        
        data_array = ope_doc.get("Data", [])
        payroll_months_rejected = set()
        
        # ✅ Reject all "approved" entries (L1 approved, now rejecting at L2)
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    # Reject entries with status "approved" (waiting for Partner L2)
                    if entry_status == "approved":
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "rejected",
                                f"Data.{i}.{month_range}.{j}.rejected_by": partner_emp_code,
                                f"Data.{i}.{month_range}.{j}.rejector_name": partner_name,
                                f"Data.{i}.{month_range}.{j}.rejected_date": current_time,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": rejection_reason,
                                f"Data.{i}.{month_range}.{j}.rejected_level": "L2"
                            }}
                        )
                        
                        payroll_months_rejected.add(month_range)
                        rejected_count += 1
                        print(f"   ❌ Rejected entry: {month_range} | Date: {entry.get('date')} | Amount: ₹{entry.get('amount')}")
        
        if rejected_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found for rejection")
        
        # ✅ Update Status collection
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_rejected:
                    # L2 (Partner) rejected
                    await db["Status"].update_one(
                        {"employeeId": employee_code},
                        {"$set": {
                            f"approval_status.{i}.L2.status": False,
                            f"approval_status.{i}.L2.rejected_by": partner_emp_code,
                            f"approval_status.{i}.L2.rejected_date": current_time,
                            f"approval_status.{i}.overall_status": "rejected",
                            f"approval_status.{i}.rejection_reason": rejection_reason,
                            f"approval_status.{i}.rejected_level": "L2"
                        }}
                    )
                    print(f"   📊 Updated Status: {ps.get('payroll_month')} → Rejected at L2")
        
        # ✅ Add to Partner_Rejected collection
        partner_rejected_doc = await db["Partner_Rejected"].find_one(
            {"PartnerEmpCode": partner_emp_code}
        )
        
        if not partner_rejected_doc:
            await db["Partner_Rejected"].insert_one({
                "PartnerEmpCode": partner_emp_code,
                "EmployeesCodes": [employee_code]
            })
            print(f"   📝 Created new Partner_Rejected document")
        else:
            if employee_code not in partner_rejected_doc.get("EmployeesCodes", []):
                await db["Partner_Rejected"].update_one(
                    {"PartnerEmpCode": partner_emp_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
                print(f"   📝 Added to Partner_Rejected collection")
        
        print(f"\n{'='*60}")
        print(f"❌ Partner rejected {rejected_count} entries for {employee_code}")
        print(f"{'='*60}\n")
        
        return {
            "message": f"Successfully rejected {rejected_count} entries",
            "rejected_count": rejected_count
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error in partner reject: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
# ---------- Serve static HTML ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")




@app.post("/api/ope/submit-final")
async def submit_final_entries(
    request: Request,
    current_user=Depends(get_current_user)
):
    try:
        employee_code = current_user["employee_code"].strip().upper()
        
        body = await request.json()
        month_range = body.get("month_range")
        
        print(f"🚀 SUBMIT FINAL: Employee {employee_code}, Month {month_range}")
        
        if not month_range:
            raise HTTPException(status_code=400, detail="month_range required")
        
        def format_month_range(month_str):
            try:
                parts = month_str.lower().split('-')
                month_map = {
                    'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
                    'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
                    'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
                }
                
                if len(parts) == 3:
                    month1 = month_map.get(parts[0], parts[0].capitalize())
                    month2 = month_map.get(parts[1], parts[1].capitalize())
                    year = parts[2]
                    return f"{month1} {year} - {month2} {year}"
                elif len(parts) == 2:
                    month = month_map.get(parts[0], parts[0].capitalize())
                    year = parts[1]
                    return f"{month} {year}"
                else:
                    return month_str
            except Exception as e:
                return month_str
        
        formatted_month_range = format_month_range(month_range)
        print(f"📅 Formatted month range: {formatted_month_range}")
        
        # Get temp data
        temp_doc = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        
        if not temp_doc:
            raise HTTPException(status_code=404, detail="No temporary data found to submit")
        
        entries_to_submit = []
        data_array = temp_doc.get("Data", [])
        
        for data_item in data_array:
            if formatted_month_range in data_item:
                entries_to_submit = data_item[formatted_month_range]
                break
        
        if not entries_to_submit:
            raise HTTPException(status_code=404, detail=f"No entries found for {formatted_month_range}")
        
        print(f"📦 Found {len(entries_to_submit)} entries to submit")
        
        # Get employee details
        emp = await db["Employee_details"].find_one({"EmpID": employee_code})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee details not found")
        
        # 🔥🔥🔥 STEP 1: CHECK IF SUBMITTER IS A REPORTING MANAGER 🔥🔥🔥
        is_reporting_manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": employee_code})
        
        # Get basic employee details
        reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
        reporting_manager_name = emp.get("ReportingEmpName", "")
        partner_code = emp.get("PartnerEmpCode", "").strip().upper()
        partner_name = emp.get("Partner", "")
        
        # ✅ CALCULATE TOTAL AMOUNT FOR NEW ENTRIES
        new_entries_amount = sum(float(entry.get("amount", 0)) for entry in entries_to_submit)
        
        # ✅ CHECK IF STATUS DOCUMENT EXISTS AND GET EXISTING TOTAL
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        existing_total = 0
        month_exists = False
        existing_month_index = -1
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") == formatted_month_range:
                    existing_total = ps.get("total_amount", 0)
                    month_exists = True
                    existing_month_index = i
                    print(f"📊 Found existing month entry with total: ₹{existing_total}")
                    break
        
        # ✅ CALCULATE CUMULATIVE TOTAL
        cumulative_total = existing_total + new_entries_amount
        
        current_time = datetime.utcnow().isoformat()
        
        # 🔥🔥🔥 APPROVAL FLOW LOGIC BASED ON SUBMITTER TYPE 🔥🔥🔥
        if is_reporting_manager:
            # 🔥 REPORTING MANAGER SUBMISSION - ALWAYS 2-LEVEL (Partner → HR)
            print(f"\n{'='*60}")
            print(f"👔 SUBMITTER IS A REPORTING MANAGER")
            print(f"   Employee Code: {employee_code}")
            print(f"   Partner: {partner_code} ({partner_name})")
            print(f"{'='*60}\n")
            
            if not partner_code:
                raise HTTPException(status_code=400, detail="No Partner assigned to this Reporting Manager")
            
            print(f"💰 RM Submission Amount: ₹{cumulative_total}")
            print(f"📊 Approval Flow: 2-level (Partner → HR) - Amount doesn't matter for RMs")
            
            total_levels = 2
            ope_label = "Reporting_Manager"
            
            # ✅ CREATE PAYROLL ENTRY FOR RM SUBMISSION
            payroll_entry = {
                "payroll_month": formatted_month_range,
                "ope_label": ope_label,
                "submitter_type": "Reporting_Manager",  # 🔥 KEY FIELD
                "total_levels": total_levels,
                "limit": 0,  # No limit for RMs
                "total_amount": cumulative_total,
                "L1": {
                    "status": False,
                    "approver_name": partner_name,
                    "approver_code": partner_code,
                    "approved_date": None,
                    "level_name": "Partner"
                },
                "L2": {
                    "status": False,
                    "approver_name": "HR",
                    "approver_code": "JHS729",
                    "approved_date": None,
                    "level_name": "HR"
                },
                "current_level": "L1",
                "overall_status": "pending",
                "submission_date": current_time
            }
            
            # 🔥 ADD TO PENDING UNDER PARTNER (NOT REPORTING MANAGER)
            pending_approver_code = partner_code
            
        else:
            # 🔥 REGULAR EMPLOYEE SUBMISSION - 2 or 3 LEVEL BASED ON LIMIT
            print(f"\n{'='*60}")
            print(f"👤 SUBMITTER IS A REGULAR EMPLOYEE")
            print(f"   Employee Code: {employee_code}")
            print(f"   Reporting Manager: {reporting_manager_code} ({reporting_manager_name})")
            print(f"{'='*60}\n")
            
            if not reporting_manager_code:
                raise HTTPException(status_code=400, detail="No reporting manager assigned")
            
            # ✅ GET OPE LIMIT FROM EMPLOYEE DETAILS COLLECTION
            ope_limit = emp.get("OPE LIMIT")
            
            if ope_limit is None:
                ope_limit = 1500
                print(f"⚠️ OPE Limit not found in Employee_details, using default: ₹{ope_limit}")
            else:
                ope_limit = float(ope_limit)
                print(f"✅ OPE Limit from Employee_details: ₹{ope_limit}")
            
            print(f"\n{'='*60}")
            print(f"💰 AMOUNT CALCULATION:")
            print(f"   Previous Total: ₹{existing_total}")
            print(f"   New Entries: +₹{new_entries_amount}")
            print(f"   Cumulative Total: ₹{cumulative_total}")
            print(f"   OPE Limit: ₹{ope_limit}")
            print(f"{'='*60}\n")
            
            # ✅ DYNAMIC APPROVAL LEVELS BASED ON CUMULATIVE TOTAL VS LIMIT
            if cumulative_total > ope_limit:
                ope_label = "Greater"
                total_levels = 3
                print(f"📊 Cumulative amount (₹{cumulative_total}) EXCEEDS limit (₹{ope_limit}) → 3-level approval required")
            else:
                ope_label = "Less"
                total_levels = 2
                print(f"📊 Cumulative amount (₹{cumulative_total}) WITHIN limit (₹{ope_limit}) → 2-level approval required")
            
            # ✅ CREATE PAYROLL ENTRY FOR EMPLOYEE SUBMISSION
            payroll_entry = {
                "payroll_month": formatted_month_range,
                "ope_label": ope_label,
                "submitter_type": "Employee",  # 🔥 KEY FIELD
                "total_levels": total_levels,
                "limit": ope_limit,
                "total_amount": cumulative_total,
                "L1": {
                    "status": False,
                    "approver_name": reporting_manager_name,
                    "approver_code": reporting_manager_code,
                    "approved_date": None,
                    "level_name": "Reporting Manager"
                },
                "L2": {
                    "status": False,
                    "approver_name": "HR" if total_levels == 2 else partner_name,
                    "approver_code": "JHS729" if total_levels == 2 else partner_code,
                    "approved_date": None,
                    "level_name": "HR" if total_levels == 2 else "Partner"
                },
                "current_level": "L1",
                "overall_status": "pending",
                "submission_date": current_time
            }
            
            # ✅ ADD L3 ONLY IF TOTAL_LEVELS = 3
            if total_levels == 3:
                payroll_entry["L3"] = {
                    "status": False,
                    "approver_name": "HR",
                    "approver_code": "JHS729",
                    "approved_date": None,
                    "level_name": "HR"
                }
                print(f"✅ Added L3 (HR) level for approval")
            
            # 🔥 ADD TO PENDING UNDER REPORTING MANAGER
            pending_approver_code = reporting_manager_code
        
        # ✅ CREATE OR UPDATE STATUS DOCUMENT
        if not status_doc:
            # ✅ CREATE NEW STATUS DOCUMENT
            new_status_doc = {
                "employeeId": employee_code,
                "employeeName": emp.get("Emp Name", ""),
                "ReportingEmpCode": reporting_manager_code, 
                "PartnerEmpCode": partner_code,  
                "HREmpCode": "JHS729", 
                "approval_status": [payroll_entry]
            }
            result = await db["Status"].insert_one(new_status_doc)
            status_doc_id = str(result.inserted_id)
            
        else:
            # ✅ UPDATE EXISTING STATUS DOCUMENT
            status_doc_id = str(status_doc["_id"])
            
            if month_exists:
                # ✅ UPDATE EXISTING MONTH WITH NEW DATA
                print(f"🔄 Updating existing month entry at index {existing_month_index}")
                
                # Build update fields dynamically
                update_fields = {
                    f"approval_status.{existing_month_index}.total_amount": cumulative_total,
                    f"approval_status.{existing_month_index}.ope_label": ope_label,
                    f"approval_status.{existing_month_index}.total_levels": total_levels,
                    f"approval_status.{existing_month_index}.submitter_type": payroll_entry["submitter_type"],
                    f"approval_status.{existing_month_index}.submission_date": current_time
                }
                
                # Add limit only for Employee submissions
                if is_reporting_manager:
                    update_fields[f"approval_status.{existing_month_index}.limit"] = 0
                else:
                    update_fields[f"approval_status.{existing_month_index}.limit"] = ope_limit
                
                # Update L2 and L3 based on total_levels
                if total_levels == 3:
                    update_fields[f"approval_status.{existing_month_index}.L3"] = {
                        "status": False,
                        "approver_name": "HR",
                        "approver_code": "JHS729",
                        "approved_date": None,
                        "level_name": "HR"
                    }
                    update_fields[f"approval_status.{existing_month_index}.L2.approver_name"] = partner_name
                    update_fields[f"approval_status.{existing_month_index}.L2.approver_code"] = partner_code
                    update_fields[f"approval_status.{existing_month_index}.L2.level_name"] = "Partner"
                else:
                    # For RM or Employee 2-level
                    if is_reporting_manager:
                        update_fields[f"approval_status.{existing_month_index}.L2.approver_name"] = "HR"
                        update_fields[f"approval_status.{existing_month_index}.L2.approver_code"] = "JHS729"
                        update_fields[f"approval_status.{existing_month_index}.L2.level_name"] = "HR"
                    else:
                        update_fields[f"approval_status.{existing_month_index}.L2.approver_name"] = "HR"
                        update_fields[f"approval_status.{existing_month_index}.L2.approver_code"] = "JHS729"
                        update_fields[f"approval_status.{existing_month_index}.L2.level_name"] = "HR"
                
                await db["Status"].update_one(
                    {"employeeId": employee_code},
                    {"$set": update_fields}
                )
                
                print(f"✅ Updated existing payroll month with cumulative total: ₹{cumulative_total}")
                
            else:
                # ✅ ADD NEW PAYROLL MONTH
                await db["Status"].update_one(
                    {"employeeId": employee_code},
                    {"$push": {"approval_status": payroll_entry}}
                )
                print(f"✅ Added new payroll month: {formatted_month_range}")
        
        # ✅ UPDATE EACH ENTRY WITH STATUS REFERENCE
        for entry in entries_to_submit:
            entry["status"] = "pending"
            entry["submitted_time"] = current_time
            entry["status_doc_id"] = status_doc_id
            entry["payroll_month"] = formatted_month_range
            entry["approved_by"] = None
            entry["approved_date"] = None
            entry["rejected_by"] = None
            entry["rejected_date"] = None
            entry["rejection_reason"] = None
        
        # ✅ Move to OPE_data collection
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            new_doc = {
                "employeeId": employee_code,
                "employeeName": emp.get("Emp Name", ""),
                "designation": emp.get("Designation Name", ""),
                "gender": emp.get("Gender", ""),
                "partner": emp.get("Partner", ""),
                "reportingManager": emp.get("ReportingEmpName", ""),
                "department": "",
                "Data": [
                    {
                        formatted_month_range: entries_to_submit
                    }
                ]
            }
            await db["OPE_data"].insert_one(new_doc)
            print(f"✅ Created new OPE_data document")
        else:
            month_exists_in_ope = False
            ope_data_array = ope_doc.get("Data", [])
            
            for i, data_item in enumerate(ope_data_array):
                if formatted_month_range in data_item:
                    for entry in entries_to_submit:
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$push": {f"Data.{i}.{formatted_month_range}": entry}}
                        )
                    month_exists_in_ope = True
                    print(f"✅ Appended to existing month in OPE_data")
                    break
            
            if not month_exists_in_ope:
                await db["OPE_data"].update_one(
                    {"employeeId": employee_code},
                    {"$push": {"Data": {formatted_month_range: entries_to_submit}}}
                )
                print(f"✅ Added new month range to OPE_data")
        
        # 🔥🔥🔥 ADD TO PENDING COLLECTION - DYNAMIC BASED ON SUBMITTER TYPE 🔥🔥🔥
        pending_doc = await db["Pending"].find_one({"ReportingEmpCode": pending_approver_code})
        
        if not pending_doc:
            await db["Pending"].insert_one({
                "ReportingEmpCode": pending_approver_code,
                "EmployeesCodes": [employee_code]
            })
            print(f"✅ Created NEW Pending document for approver {pending_approver_code}")
        else:
            if employee_code not in pending_doc.get("EmployeesCodes", []):
                await db["Pending"].update_one(
                    {"ReportingEmpCode": pending_approver_code},
                    {"$addToSet": {"EmployeesCodes": employee_code}}
                )
                print(f"✅ Added employee to Pending list under {pending_approver_code}")
        
        # ✅ Delete from Temp_OPE_data
        temp_data_array = temp_doc.get("Data", [])
        
        for i, data_item in enumerate(temp_data_array):
            if formatted_month_range in data_item:
                await db["Temp_OPE_data"].update_one(
                    {"employeeId": employee_code},
                    {"$pull": {"Data": {formatted_month_range: {"$exists": True}}}}
                )
                print(f"✅ Removed from Temp_OPE_data")
                break
        
        # If no more temp data, delete document
        updated_temp = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        if updated_temp and len(updated_temp.get("Data", [])) == 0:
            await db["Temp_OPE_data"].delete_one({"employeeId": employee_code})
            print(f"✅ Deleted empty Temp_OPE_data document")
        
        print(f"\n{'='*60}")
        print(f"✅✅ SUBMISSION COMPLETE ✅✅")
        print(f"   Submitter Type: {'REPORTING MANAGER' if is_reporting_manager else 'EMPLOYEE'}")
        print(f"   Employee: {employee_code}")
        print(f"   Previous Total: ₹{existing_total}")
        print(f"   New Entries: +₹{new_entries_amount}")
        print(f"   Cumulative Total: ₹{cumulative_total}")
        print(f"   Approval Levels: {total_levels}")
        print(f"   First Approver: {pending_approver_code}")
        print(f"{'='*60}\n")
        
        return {
            "message": "Entries submitted successfully for approval",
            "submitted_count": len(entries_to_submit),
            "month_range": formatted_month_range,
            "submitter_type": "Reporting_Manager" if is_reporting_manager else "Employee",
            "first_approver": pending_approver_code,
            "previous_total": existing_total,
            "new_entries_amount": new_entries_amount,
            "total_amount": cumulative_total,
            "ope_limit": 0 if is_reporting_manager else ope_limit,
            "ope_label": ope_label,
            "total_levels": total_levels,
            "status": "pending_approval"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error submitting final: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
