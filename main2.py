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
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES"))

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ---------- FastAPI app ----------
app = FastAPI()

# CORS (agar HTML ko alag port se serve kar rahe ho)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prod me restrict karna
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Mongo Connection ----------
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]
user_collection = db["user"]   # exactly same as Compass me dikh raha hai


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


# Ye wali Employee Details check kr ke Login Hone degi abhi Employee Details hai to upper wali/ Details aane ke bad usko dlt kr kr niche wali chlan h

# @app.post("/api/register")
# async def register(user: UserCreate):

#     # 1️⃣ Check if employee exists in Master / Employee_details
#     valid = await is_valid_employee(user.employee_code)
#     if not valid:
#         raise HTTPException(
#             status_code=400,
#             detail="Employee ID does not exist in company records"
#         )

#     # 2️⃣ Check if already registered
#     existing = await user_collection.find_one({"employee_code": user.employee_code})
#     if existing:
#         raise HTTPException(
#             status_code=400,
#             detail="Employee already registered"
#         )

#     # 3️⃣ Hash password
#     hashed_password = get_password_hash(user.password)

#     # 4️⃣ Insert into user collection
#     doc = {
#         "employee_code": user.employee_code,
#         "password_hash": hashed_password,
#         "created_at": datetime.utcnow()
#     }

#     await user_collection.insert_one(doc)

#     return {"message": "Registered successfully"}


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
        "reporting_manager_name": emp.get("ReportingEmpName")
    }


# ---------- OPE Data Submission ----------
# Replace complete /api/ope/submit endpoint in main.py

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
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
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
    Get all employees under a reporting manager with pending entries
    """
    try:
        reporting_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"🔍 Fetching pending employees for manager: {reporting_emp_code}")
        
        # Verify user is a manager
        manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
        if not manager:
            raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
        # Get all employees under this manager from Employee_details
        employees = await db["Employee_details"].find(
            {"ReportingEmpCode": reporting_emp_code}
        ).to_list(length=None)
        
        print(f"👥 Found {len(employees)} employees under manager")
        
        pending_employees = []
        
        for emp in employees:
            emp_code = emp.get("EmpID")
            emp_name = emp.get("Emp Name")
            
            # Get OPE data for this employee
            ope_doc = await db["OPE_data"].find_one({"employeeId": emp_code})
            
            if ope_doc:
                # Collect all pending entries
                pending_entries = []
                data_array = ope_doc.get("Data", [])
                
                for data_item in data_array:
                    for month_range, entries in data_item.items():
                        for entry in entries:
                            # Check if status is pending or not set
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
                
                # Only add employee if they have pending entries
                if pending_entries:
                    pending_employees.append({
                        "employeeId": emp_code,
                        "employeeName": emp_name,
                        "designation": emp.get("Designation Name", ""),
                        "pendingCount": len(pending_entries),
                        "entries": pending_entries
                    })
        
        print(f"✅ Found {len(pending_employees)} employees with pending entries")
        
        return {
            "reporting_manager": reporting_emp_code,
            "total_employees": len(pending_employees),
            "employees": pending_employees
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error fetching pending employees: {str(e)}")
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
        
        # ✅ CHECK 1: Is user accessing their own data?
        is_own_data = (current_emp_code == employee_code)
        
        # ✅ CHECK 2: Is current user a manager?
        is_manager = await db["Reporting_managers"].find_one(
            {"ReportingEmpCode": current_emp_code}
        )
        
        # ✅ CHECK 3: If not own data and not manager, DENY
        if not is_own_data and not is_manager:
            print(f"❌ Access denied - Not own data and not a manager")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # ✅ CHECK 4: If manager, verify employee reports to them (optional - remove if causing issues)
        if is_manager and not is_own_data:
            employee_details = await db["Employee_details"].find_one(
                {"EmpID": employee_code}
            )
            
            if not employee_details:
                print(f"❌ Employee not found in Employee_details")
                raise HTTPException(status_code=404, detail="Employee not found")
            
            # ✅ REMOVED STRICT CHECK - Allow any manager to view any employee's approved data
            print(f"✅ Manager access granted")
        
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
                            "employee_name": ope_doc.get("employeeName", ""),  # ✅ ADD THIS
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
                            "approver_name": entry.get("approver_name"),  # ✅ KEY FIELD
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
        
        # ✅ CHECK 1: Is user accessing their own data?
        is_own_data = (current_emp_code == employee_code)
        
        # ✅ CHECK 2: Is current user a manager?
        is_manager = await db["Reporting_managers"].find_one(
            {"ReportingEmpCode": current_emp_code}
        )
        
        # ✅ CHECK 3: If not own data and not manager, DENY
        if not is_own_data and not is_manager:
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
                            "rejector_name": entry.get("rejector_name"),  # ✅ KEY FIELD
                            "rejected_date": entry.get("rejected_date"),
                            "rejection_reason": entry.get("rejection_reason"),
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
        temp_doc = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        
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
# SUBMIT FINAL - Move from Temp_OPE_data to OPE_data
# ============================================
# ============================================
# SUBMIT FINAL - Move from Temp_OPE_data to OPE_data
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
        
        # ✅ STEP 1: Get temp data
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
        
        # ✅ STEP 2: Get employee details
        emp = await db["Employee_details"].find_one({"EmpID": employee_code})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee details not found")
        
        reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
        reporting_manager_name = emp.get("ReportingEmpName", "")
        partner = emp.get("Partner", "")
        
        if not reporting_manager_code:
            raise HTTPException(status_code=400, detail="No reporting manager assigned")
        
        print(f"👔 Reporting Manager: {reporting_manager_code} ({reporting_manager_name})")
        
        # ✅ STEP 3: Create Status documents (one per entry)
        current_time = datetime.utcnow().isoformat()
        submitted_count = 0
        
        for entry in entries_to_submit:
            status_id = ObjectId()
            
            status_doc = {
                "_id": status_id,
                "employeeId": employee_code,
                "employeeName": emp.get("Emp Name", ""),
                "month_range": formatted_month_range,
                "submission_date": current_time,
                "L1": {
                    "status": False,
                    "approver_name": reporting_manager_name,
                    "approver_code": reporting_manager_code,
                    "approved_date": None,
                    "level_name": "Reporting Manager"
                },
                "L2": {
                    "status": False,
                    "approver_name": partner,
                    "approver_code": "",
                    "approved_date": None,
                    "level_name": "Partner"
                },
                "L3": {
                    "status": False,
                    "approver_name": "HR",
                    "approver_code": "",
                    "approved_date": None,
                    "level_name": "HR"
                },
                "current_level": "L1",
                "overall_status": "pending"
            }
            
            # Insert into Status collection
            await db["Status"].insert_one(status_doc)
            
            # ✅ STEP 4: Update entry with status reference
            entry["status"] = "pending"
            entry["submitted_time"] = current_time
            entry["status_id"] = str(status_id)
            entry["approved_by"] = None
            entry["approved_date"] = None
            entry["rejected_by"] = None
            entry["rejected_date"] = None
            entry["rejection_reason"] = None
            
            print(f"✅ Status doc created for entry: {status_id}")
        
        # ✅ STEP 5: Move to OPE_data collection
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
            month_exists = False
            ope_data_array = ope_doc.get("Data", [])
            
            for i, data_item in enumerate(ope_data_array):
                if formatted_month_range in data_item:
                    for entry in entries_to_submit:
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$push": {f"Data.{i}.{formatted_month_range}": entry}}
                        )
                    month_exists = True
                    print(f"✅ Appended to existing month in OPE_data")
                    break
            
            if not month_exists:
                await db["OPE_data"].update_one(
                    {"employeeId": employee_code},
                    {"$push": {"Data": {formatted_month_range: entries_to_submit}}}
                )
                print(f"✅ Added new month range to OPE_data")
        
        # ✅ STEP 6: Add to PENDING collection (MOST IMPORTANT)
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
        
        # ✅ STEP 7: Delete from Temp_OPE_data
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
        
        print(f"\n✅✅ SUBMISSION COMPLETE ✅✅\n")
        
        return {
            "message": "Entries submitted successfully for approval",
            "submitted_count": len(entries_to_submit),
            "month_range": formatted_month_range,
            "reporting_manager": reporting_manager_code,
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
        print(f"✅ APPROVAL REQUEST")
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
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    if entry_status != "pending":
                        continue
                    
                    # ✅ APPROVE THIS ENTRY WITH PROPER FIELDS
                    await db["OPE_data"].update_one(
                        {"employeeId": employee_code},
                        {"$set": {
                            f"Data.{i}.{month_range}.{j}.status": "approved",
                            f"Data.{i}.{month_range}.{j}.approved_date": current_time,
                            f"Data.{i}.{month_range}.{j}.approved_by": reporting_emp_code,
                            f"Data.{i}.{month_range}.{j}.approver_name": manager_name  # ✅ KEY FIX
                        }}
                    )
                    
                    # Update Status collection
                    status_id = entry.get("status_id")
                    if status_id:
                        await db["Status"].update_one(
                            {"_id": ObjectId(status_id)},
                            {"$set": {
                                "L1.status": True,
                                "L1.approver_code": reporting_emp_code,
                                "L1.approver_name": manager_name,
                                "L1.approved_date": current_time,
                                "overall_status": "approved"
                            }}
                        )
                    
                    approved_count += 1
        
        if approved_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found")
        
        # ✅ REMOVE FROM PENDING
        await db["Pending"].update_one(
            {"ReportingEmpCode": emp_reporting_manager_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        print(f"✅ Removed from Pending")
        
        # ✅ ADD TO APPROVED (UNDER CURRENT MANAGER)
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
                print(f"✅ Added to Approved collection")
        
        return {
            "message": f"Approved {approved_count} entries",
            "approved_count": approved_count,
            "employee_code": employee_code
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
    Get approval status for all entries of an employee
    """
    try:
        employee_code = employee_code.strip().upper()
        current_emp_code = current_user["employee_code"].strip().upper()
        
        print(f"📊 Fetching status for: {employee_code}")
        
        if current_emp_code != employee_code:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get all Status documents for this employee
        status_docs = await db["Status"].find({"employeeId": employee_code}).to_list(length=None)
        
        print(f"📊 Found {len(status_docs)} status documents in Status collection")
        
        if not status_docs:
            return {"status_entries": []}
        
        # Get OPE_data to get entry details
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            return {"status_entries": []}
        
        status_entries = []
        
        # For each status document, find matching entry in OPE_data
        for status_doc in status_docs:
            status_id = str(status_doc["_id"])
            
            # Search for entry with this status_id
            data_array = ope_doc.get("Data", [])
            
            for data_item in data_array:
                for month_range, entries in data_item.items():
                    for entry in entries:
                        if str(entry.get("status_id")) == status_id:
                            status_entries.append({
                                "_id": str(entry.get("_id", "")),
                                "status_id": status_id,
                                "month_range": month_range,
                                "date": entry.get("date"),
                                "client": entry.get("client"),
                                "project_id": entry.get("project_id"),
                                "project_name": entry.get("project_name"),
                                "amount": entry.get("amount"),
                                "overall_status": status_doc.get("overall_status", "pending"),
                                "current_level": status_doc.get("current_level", "L1"),
                                "L1": status_doc.get("L1", {}),
                                "L2": status_doc.get("L2", {}),
                                "L3": status_doc.get("L3", {}),
                                "submitted_time": entry.get("submitted_time")
                            })
                            break
        
        print(f"✅ Returning {len(status_entries)} status entries")
        return {"status_entries": status_entries}
        
    except Exception as e:
        print(f"❌ Error fetching status: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Serve static HTML ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")



