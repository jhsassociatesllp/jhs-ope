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
        "reporting_manager_name": emp.get("ReportingEmpName"),
        "ope_limit": emp.get("OPE Limit")
    }


# ---------- OPE Data Submission ----------
# Replace complete /api/ope/submit endpoint in main.py

# @app.post("/api/ope/submit")
# async def submit_ope_entry(
#     date: str = Form(...),
#     client: str = Form(...),
#     project_id: str = Form(...),
#     project_name: str = Form(...),
#     project_type: str = Form(...),
#     location_from: str = Form(...),
#     location_to: str = Form(...),
#     travel_mode: str = Form(...),
#     amount: float = Form(...),
#     remarks: str = Form(...),
#     month_range: str = Form(...),
#     ticket_pdf: Optional[UploadFile] = File(None),
#     current_user=Depends(get_current_user)
# ):
#     try:
#         employee_code = current_user["employee_code"]
        
#         print(f"📌 Submitting OPE entry for: {employee_code}")
#         print(f"📌 Month range received: {month_range}")
#         print(f"📌 Project type: {project_type}")
#         print(f"📌 Date: {date}")
#         print(f"📌 Amount: {amount}")
        
#         # Validate amount
#         if amount <= 0:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Amount must be greater than 0, received: {amount}"
#             )
        
#         # Format month_range from "sep-oct-2025" to "Sep 2025 - Oct 2025"
#         def format_month_range(month_str):
#             """
#             Convert "sep-oct-2025" to "Sep 2025 - Oct 2025"
#             Convert "jan-2025" to "Jan 2025"
#             """
#             try:
#                 parts = month_str.lower().split('-')
                
#                 # Month mapping
#                 month_map = {
#                     'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
#                     'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
#                     'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
#                 }
                
#                 if len(parts) == 3:  # e.g., "sep-oct-2025"
#                     month1 = month_map.get(parts[0], parts[0].capitalize())
#                     month2 = month_map.get(parts[1], parts[1].capitalize())
#                     year = parts[2]
#                     return f"{month1} {year} - {month2} {year}"
#                 elif len(parts) == 2:  # e.g., "jan-2025"
#                     month = month_map.get(parts[0], parts[0].capitalize())
#                     year = parts[1]
#                     return f"{month} {year}"
#                 else:
#                     return month_str  # Return as-is if format unexpected
#             except Exception as e:
#                 print(f"⚠️ Error formatting month range: {e}")
#                 return month_str
        
#         formatted_month_range = format_month_range(month_range)
#         print(f"✅ Formatted month range: {formatted_month_range}")
        
#         # Get employee details
#         emp = await db["Employee_details"].find_one({"EmpID": employee_code})
#         if not emp:
#             print(f"❌ Employee not found: {employee_code}")
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"Employee details not found for code: {employee_code}"
#             )
        
#         print(f"✅ Employee found: {emp.get('Emp Name')}")
        
#         # Handle PDF file
#         pdf_base64 = None
#         if ticket_pdf:
#             pdf_content = await ticket_pdf.read()
#             pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
#             print(f"✅ PDF uploaded: {ticket_pdf.filename}")
        
#         # Create entry document
#         entry_doc = {
#             "_id": ObjectId(),
#             "date": date,
#             "client": client,
#             "project_id": project_id,
#             "project_name": project_name,
#             "project_type": project_type,
#             "location_from": location_from,
#             "location_to": location_to,
#             "travel_mode": travel_mode,
#             "amount": amount,
#             "remarks": remarks,
#             "ticket_pdf": pdf_base64,
#             "created_time": datetime.utcnow().isoformat(),
#             "updated_time": datetime.utcnow().isoformat()
#         }
        
#         print(f"📝 Entry doc created: {entry_doc['date']}")
        
#         # Find employee document in OPE_data
#         ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
#         if not ope_doc:
#             print(f"🆕 Creating NEW OPE document for {employee_code}")
#             # Create new document with FORMATTED month range
#             new_doc = {
#                 "employeeId": employee_code,
#                 "employeeName": emp.get("Emp Name", ""),
#                 "designation": emp.get("Designation Name", ""),
#                 "gender": emp.get("Gender", ""),
#                 "partner": emp.get("Partner", ""),
#                 "reportingManager": emp.get("ReportingEmpName", ""),
#                 "department": "",
#                 "Data": [
#                     {
#                         formatted_month_range: [entry_doc]
#                     }
#                 ]
#             }
#             result = await db["OPE_data"].insert_one(new_doc)
#             print(f"✅ NEW document inserted with ID: {result.inserted_id}")
            
#         else:
#             print(f"📂 Found existing OPE document for {employee_code}")
#             # Check if formatted month_range exists in Data
#             month_exists = False
#             data_array = ope_doc.get("Data", [])
            
#             for i, data_item in enumerate(data_array):
#                 if formatted_month_range in data_item:
#                     print(f"✅ Month range '{formatted_month_range}' exists, appending entry")
#                     # Append to existing month using $push
#                     await db["OPE_data"].update_one(
#                         {"employeeId": employee_code},
#                         {"$push": {f"Data.{i}.{formatted_month_range}": entry_doc}}
#                     )
#                     month_exists = True
#                     break
            
#             if not month_exists:
#                 print(f"🆕 Month range '{formatted_month_range}' NOT found, creating new")
#                 # Add new month range using $push with FORMATTED version
#                 await db["OPE_data"].update_one(
#                     {"employeeId": employee_code},
#                     {"$push": {"Data": {formatted_month_range: [entry_doc]}}}
#                 )
        
#         print(f"✅✅ Entry submitted successfully!")
        
#         # Verify data was saved
#         verify_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
#         print(f"🔍 Verification - Data array length: {len(verify_doc.get('Data', []))}")
        
#         return {
#             "message": "Entry submitted successfully",
#             "employee_id": employee_code,
#             "date": date,
#             "month_range": formatted_month_range,
#             "project_type": project_type,
#             "status": "saved"
#         }
        
#     except HTTPException as he:
#         # Re-raise HTTP exceptions as-is
#         raise he
#     except Exception as e:
#         print(f"❌❌ Error submitting OPE entry: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(
#             status_code=500,
#             detail=f"Database error: {str(e)}"
#         )

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

# @app.get("/api/ope/manager/pending")
# async def get_manager_pending_employees(current_user=Depends(get_current_user)):
#     """
#     Get all employees under a reporting manager with pending entries
#     """
#     try:
#         reporting_emp_code = current_user["employee_code"].strip().upper()
        
#         print(f"🔍 Fetching pending employees for manager: {reporting_emp_code}")
        
#         # Verify user is a manager
#         manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
#         if not manager:
#             raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
#         # Get all employees under this manager from Employee_details
#         employees = await db["Employee_details"].find(
#             {"ReportingEmpCode": reporting_emp_code}
#         ).to_list(length=None)
        
#         print(f"👥 Found {len(employees)} employees under manager")
        
#         pending_employees = []
        
#         for emp in employees:
#             emp_code = emp.get("EmpID")
#             emp_name = emp.get("Emp Name")
            
#             # Get OPE data for this employee
#             ope_doc = await db["OPE_data"].find_one({"employeeId": emp_code})
            
#             if ope_doc:
#                 # Collect all pending entries
#                 pending_entries = []
#                 data_array = ope_doc.get("Data", [])
                
#                 for data_item in data_array:
#                     for month_range, entries in data_item.items():
#                         for entry in entries:
#                             # Check if status is pending or not set
#                             entry_status = entry.get("status", "pending").lower()
#                             if entry_status == "pending":
#                                 pending_entries.append({
#                                     "_id": str(entry.get("_id", "")),
#                                     "month_range": month_range,
#                                     "date": entry.get("date"),
#                                     "client": entry.get("client"),
#                                     "project_id": entry.get("project_id"),
#                                     "project_name": entry.get("project_name"),
#                                     "project_type": entry.get("project_type", "N/A"),
#                                     "location_from": entry.get("location_from"),
#                                     "location_to": entry.get("location_to"),
#                                     "travel_mode": entry.get("travel_mode"),
#                                     "amount": entry.get("amount"),
#                                     "remarks": entry.get("remarks"),
#                                     "ticket_pdf": entry.get("ticket_pdf")
#                                 })
                
#                 # Only add employee if they have pending entries
#                 if pending_entries:
#                     pending_employees.append({
#                         "employeeId": emp_code,
#                         "employeeName": emp_name,
#                         "designation": emp.get("Designation Name", ""),
#                         "pendingCount": len(pending_entries),
#                         "entries": pending_entries
#                     })
        
#         print(f"✅ Found {len(pending_employees)} employees with pending entries")
        
#         return {
#             "reporting_manager": reporting_emp_code,
#             "total_employees": len(pending_employees),
#             "employees": pending_employees
#         }
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         print(f"❌ Error fetching pending employees: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))

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
            
            # ✅ GET ALL STATUS DOCUMENTS WHERE CURRENT_LEVEL IS L2 OR L3
            status_docs = await db["Status"].find({
                "$or": [
                    {"approval_status.current_level": "L2"},
                    {"approval_status.current_level": "L3"}
                ]
            }).to_list(length=None)
            
            print(f"📊 Found {len(status_docs)} employees with entries pending HR approval")
            
            pending_employees = []
            
            for status_doc in status_docs:
                employee_id = status_doc.get("employeeId")
                employee_name = status_doc.get("employeeName")
                approval_status = status_doc.get("approval_status", [])
                
                # Get OPE data for this employee
                ope_doc = await db["OPE_data"].find_one({"employeeId": employee_id})
                
                if not ope_doc:
                    continue
                
                pending_entries = []
                
                # ✅ FILTER ENTRIES BASED ON APPROVAL STATUS
                for ps in approval_status:
                    current_level = ps.get("current_level")
                    payroll_month = ps.get("payroll_month")
                    total_levels = ps.get("total_levels", 2)
                    
                    # ✅ HR should see entries where:
                    # - For 2-level: current_level = "L2" and L1.status = True
                    # - For 3-level: current_level = "L3" and L1.status = True and L2.status = True
                    
                    L1_approved = ps.get("L1", {}).get("status", False)
                    L2_approved = ps.get("L2", {}).get("status", False) if total_levels == 3 else True
                    
                    should_show = False
                    
                    if total_levels == 2 and current_level == "L2" and L1_approved:
                        should_show = True
                    elif total_levels == 3 and current_level == "L3" and L1_approved and L2_approved:
                        should_show = True
                    
                    if should_show:
                        # Find entries for this payroll month
                        data_array = ope_doc.get("Data", [])
                        
                        for data_item in data_array:
                            if payroll_month in data_item:
                                entries = data_item[payroll_month]
                                
                                for entry in entries:
                                    # ✅ Only show entries with status "approved" (by L1/L2)
                                    if entry.get("status", "").lower() == "approved":
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
                
                if pending_entries:
                    pending_employees.append({
                        "employeeId": employee_id,
                        "employeeName": employee_name,
                        "designation": ope_doc.get("designation", ""),
                        "pendingCount": len(pending_entries),
                        "entries": pending_entries
                    })
            
            print(f"✅ Returning {len(pending_employees)} employees for HR")
            
            return {
                "reporting_manager": current_emp_code,
                "is_hr": True,
                "total_employees": len(pending_employees),
                "employees": pending_employees
            }
        
        else:
            # ✅ ORIGINAL LOGIC FOR REPORTING MANAGERS
            print(f"👔 USER IS REPORTING MANAGER")
            
            # Verify user is a manager
            manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": current_emp_code})
            if not manager:
                raise HTTPException(status_code=403, detail="You are not a reporting manager")
            
            # Get all employees under this manager
            employees = await db["Employee_details"].find(
                {"ReportingEmpCode": current_emp_code}
            ).to_list(length=None)
            
            print(f"👥 Found {len(employees)} employees under manager")
            
            pending_employees = []
            
            for emp in employees:
                emp_code = emp.get("EmpID")
                emp_name = emp.get("Emp Name")
                
                # Get OPE data
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
        
        # ✅ CHECK 1: Is user accessing their own data?
        is_own_data = (current_emp_code == employee_code)
        
        # ✅ CHECK 2: Is current user HR?
        is_hr = (current_emp_code == "JHS729")
        
        # ✅ CHECK 3: Is current user a manager?
        is_manager = await db["Reporting_managers"].find_one(
            {"ReportingEmpCode": current_emp_code}
        )
        
        # ✅ ALLOW ACCESS IF: own data OR HR OR manager
        if not is_own_data and not is_hr and not is_manager:
            print(f"❌ Access denied - Not own data, not HR, and not a manager")
            raise HTTPException(status_code=403, detail="Access denied")
        
        print(f"✅ Access granted (Own: {is_own_data}, HR: {is_hr}, Manager: {bool(is_manager)})")
        
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
                    
                    # ✅ ONLY APPROVED ENTRIES
                    if entry_status == "approved":
                        approved_entries.append({
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
                            "approved_by": entry.get("approved_by"),
                            "approver_name": entry.get("approver_name"),
                            "approved_date": entry.get("approved_date"),
                            "created_time": entry.get("created_time"),
                            # ✅ NEW: HR approval info
                            "hr_approved": entry.get("hr_approved", False),
                            "hr_approved_by": entry.get("hr_approved_by"),
                            "hr_approved_date": entry.get("hr_approved_date")
                        })
        
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
        
        # ✅ CHECK 2: Is current user HR?
        is_hr = (current_emp_code == "JHS729")
        
        # ✅ CHECK 3: Is current user a manager?
        is_manager = await db["Reporting_managers"].find_one(
            {"ReportingEmpCode": current_emp_code}
        )
        
        # ✅ ALLOW ACCESS IF: own data OR HR OR manager
        if not is_own_data and not is_hr and not is_manager:
            print(f"❌ Access denied")
            raise HTTPException(status_code=403, detail="Access denied")
        
        print(f"✅ Access granted (Own: {is_own_data}, HR: {is_hr}, Manager: {bool(is_manager)})")
        
        # ✅ FETCH OPE DATA
        ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
        if not ope_doc:
            print(f"📭 No OPE data found for {employee_code}")
            return {"rejected": []}
        
        print(f"✅ OPE document found")
        
        # ✅ FLATTEN AND FILTER REJECTED ENTRIES
        rejected_entries = []
        data_array = ope_doc.get("Data", [])
        
        for data_item in data_array:
            for month_range, entries in data_item.items():
                for entry in entries:
                    entry_status = entry.get("status", "").lower()
                    
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
                            "rejector_name": entry.get("rejector_name"),
                            "rejected_date": entry.get("rejected_date"),
                            "rejection_reason": entry.get("rejection_reason"),
                            "created_time": entry.get("created_time")
                        })
        
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
        print(f"Current user: {reporting_emp_code}")
        print(f"Employee: {employee_code}")
        print(f"Reason: {rejection_reason}")
        print(f"{'='*60}\n")
        
        # ✅ CHECK IF USER IS HR
        is_hr = (reporting_emp_code == "JHS729")
        
        # Get manager details (if not HR)
        manager_name = "HR"
        if not is_hr:
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
        
        # ✅ UPDATE ALL APPROVED ENTRIES TO REJECTED (NOT PENDING)
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
                    # ✅ REJECT ONLY APPROVED ENTRIES (HR rejects approved, Manager rejects pending)
                    if (is_hr and entry_status == "approved") or (not is_hr and entry_status == "pending"):
                        # Update entry status
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.status": "rejected",
                                f"Data.{i}.{month_range}.{j}.rejected_by": reporting_emp_code,
                                f"Data.{i}.{month_range}.{j}.rejector_name": manager_name,
                                f"Data.{i}.{month_range}.{j}.rejected_date": current_time,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": rejection_reason
                            }}
                        )
                        
                        # Update Status collection
                        status_id = entry.get("status_id")
                        if status_id:
                            # ✅ Determine which level to update
                            rejection_level = "L3" if is_hr else "L1"
                            
                            await db["Status"].update_one(
                                {"_id": ObjectId(status_id)},
                                {"$set": {
                                    "overall_status": "rejected",
                                    f"{rejection_level}.status": False,
                                    f"{rejection_level}.rejected_by": reporting_emp_code,
                                    f"{rejection_level}.rejected_date": current_time
                                }}
                            )
                        
                        rejected_count += 1
                        print(f"✅ Rejected entry {j + 1}")
        
        if rejected_count == 0:
            raise HTTPException(status_code=404, detail="No entries found to reject")
        
        print(f"\n✅ Total entries rejected: {rejected_count}")
        
        # ✅ REMOVE FROM PENDING (only if manager is rejecting)
        if not is_hr:
            await db["Pending"].update_one(
                {"ReportingEmpCode": emp_reporting_manager_code},
                {"$pull": {"EmployeesCodes": employee_code}}
            )
            print(f"✅ Removed from Pending collection")
        
        # ✅ REMOVE FROM APPROVED (if HR is rejecting)
        if is_hr:
            # HR might have this employee in their approved list
            await db["Approved"].update_many(
                {},
                {"$pull": {"EmployeesCodes": employee_code}}
            )
            print(f"✅ Removed from Approved collections")
        
        # ✅ ADD TO REJECTED (UNDER CURRENT USER'S CODE)
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
            "employee_code": employee_code,
            "rejected_by": "HR" if is_hr else "Manager"
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
# SUBMIT FINAL - Move from Temp_OPE_data to OPE_data
# ============================================
# @app.post("/api/ope/submit-final")
# async def submit_final_entries(
#     request: Request,
#     current_user=Depends(get_current_user)
# ):
#     try:
#         employee_code = current_user["employee_code"].strip().upper()
        
#         body = await request.json()
#         month_range = body.get("month_range")
        
#         print(f"🚀 SUBMIT FINAL: Employee {employee_code}, Month {month_range}")
        
#         if not month_range:
#             raise HTTPException(status_code=400, detail="month_range required")
        
#         def format_month_range(month_str):
#             try:
#                 parts = month_str.lower().split('-')
#                 month_map = {
#                     'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
#                     'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
#                     'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
#                 }
                
#                 if len(parts) == 3:
#                     month1 = month_map.get(parts[0], parts[0].capitalize())
#                     month2 = month_map.get(parts[1], parts[1].capitalize())
#                     year = parts[2]
#                     return f"{month1} {year} - {month2} {year}"
#                 elif len(parts) == 2:
#                     month = month_map.get(parts[0], parts[0].capitalize())
#                     year = parts[1]
#                     return f"{month} {year}"
#                 else:
#                     return month_str
#             except Exception as e:
#                 return month_str
        
#         formatted_month_range = format_month_range(month_range)
#         print(f"📅 Formatted month range: {formatted_month_range}")
        
#         # Get temp data
#         temp_doc = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
        
#         if not temp_doc:
#             raise HTTPException(status_code=404, detail="No temporary data found to submit")
        
#         entries_to_submit = []
#         data_array = temp_doc.get("Data", [])
        
#         for data_item in data_array:
#             if formatted_month_range in data_item:
#                 entries_to_submit = data_item[formatted_month_range]
#                 break
        
#         if not entries_to_submit:
#             raise HTTPException(status_code=404, detail=f"No entries found for {formatted_month_range}")
        
#         print(f"📦 Found {len(entries_to_submit)} entries to submit")
        
#         # Get employee details
#         emp = await db["Employee_details"].find_one({"EmpID": employee_code})
#         if not emp:
#             raise HTTPException(status_code=404, detail="Employee details not found")
        
#         reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
#         reporting_manager_name = emp.get("ReportingEmpName", "")
#         partner = emp.get("Partner", "")
        
#         if not reporting_manager_code:
#             raise HTTPException(status_code=400, detail="No reporting manager assigned")
        
#         print(f"👔 Reporting Manager: {reporting_manager_code} ({reporting_manager_name})")
        
#         # ✅ Calculate total amount for this month
#         total_amount = sum(float(entry.get("amount", 0)) for entry in entries_to_submit)
        
#         # ✅ Determine OPE label and levels based on amount
#         if total_amount > 5000:  # Example threshold - adjust as needed
#             ope_label = "Greater"
#             total_levels = 3
#         else:
#             ope_label = "Less"
#             total_levels = 2
        
#         current_time = datetime.utcnow().isoformat()
        
#         # ✅ CREATE OR UPDATE STATUS DOCUMENT (ONE PER EMPLOYEE)
#         status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
#         # Create payroll entry
#         payroll_entry = {
#             "payroll_month": formatted_month_range,
#             "ope_label": ope_label,
#             "total_levels": total_levels,
#             "limit": 5000,  # Set your limit here
#             "total_amount": total_amount,
#             "L1": {
#                 "status": False,
#                 "approver_name": reporting_manager_name,
#                 "approver_code": reporting_manager_code,
#                 "approved_date": None,
#                 "level_name": "Reporting Manager"
#             },
#             "L2": {
#                 "status": False,
#                 "approver_name": partner,
#                 "approver_code": "",
#                 "approved_date": None,
#                 "level_name": "Partner"
#             },
#             "current_level": "L1",
#             "overall_status": "pending",
#             "submission_date": current_time
#         }
        
#         # ✅ Add L3 only if total_levels = 3
#         if total_levels == 3:
#             payroll_entry["L3"] = {
#                 "status": False,
#                 "approver_name": "HR",
#                 "approver_code": "",
#                 "approved_date": None,
#                 "level_name": "HR"
#             }
        
#         if not status_doc:
#             # ✅ CREATE NEW STATUS DOCUMENT
#             new_status_doc = {
#                 "employeeId": employee_code,
#                 "employeeName": emp.get("Emp Name", ""),
#                 "approval_status": [payroll_entry]
#             }
#             result = await db["Status"].insert_one(new_status_doc)
#             status_doc_id = str(result.inserted_id)
#             print(f"✅ Created NEW Status document: {status_doc_id}")
#         else:
#             # ✅ UPDATE EXISTING STATUS DOCUMENT - ADD NEW PAYROLL MONTH
#             status_doc_id = str(status_doc["_id"])
            
#             # Check if this payroll month already exists
#             approval_status = status_doc.get("approval_status", [])
#             month_exists = False
            
#             for i, ps in enumerate(approval_status):
#                 if ps.get("payroll_month") == formatted_month_range:
#                     # Update existing month
#                     await db["Status"].update_one(
#                         {"employeeId": employee_code},
#                         {"$set": {f"approval_status.{i}": payroll_entry}}
#                     )
#                     month_exists = True
#                     print(f"✅ Updated existing payroll month: {formatted_month_range}")
#                     break
            
#             if not month_exists:
#                 # Add new payroll month
#                 await db["Status"].update_one(
#                     {"employeeId": employee_code},
#                     {"$push": {"approval_status": payroll_entry}}
#                 )
#                 print(f"✅ Added new payroll month: {formatted_month_range}")
        
#         # ✅ UPDATE EACH ENTRY WITH STATUS REFERENCE
#         for entry in entries_to_submit:
#             entry["status"] = "pending"
#             entry["submitted_time"] = current_time
#             entry["status_doc_id"] = status_doc_id
#             entry["payroll_month"] = formatted_month_range
#             entry["approved_by"] = None
#             entry["approved_date"] = None
#             entry["rejected_by"] = None
#             entry["rejected_date"] = None
#             entry["rejection_reason"] = None
        
#         # ✅ Move to OPE_data collection
#         ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
#         if not ope_doc:
#             new_doc = {
#                 "employeeId": employee_code,
#                 "employeeName": emp.get("Emp Name", ""),
#                 "designation": emp.get("Designation Name", ""),
#                 "gender": emp.get("Gender", ""),
#                 "partner": emp.get("Partner", ""),
#                 "reportingManager": emp.get("ReportingEmpName", ""),
#                 "department": "",
#                 "Data": [
#                     {
#                         formatted_month_range: entries_to_submit
#                     }
#                 ]
#             }
#             await db["OPE_data"].insert_one(new_doc)
#             print(f"✅ Created new OPE_data document")
#         else:
#             month_exists = False
#             ope_data_array = ope_doc.get("Data", [])
            
#             for i, data_item in enumerate(ope_data_array):
#                 if formatted_month_range in data_item:
#                     for entry in entries_to_submit:
#                         await db["OPE_data"].update_one(
#                             {"employeeId": employee_code},
#                             {"$push": {f"Data.{i}.{formatted_month_range}": entry}}
#                         )
#                     month_exists = True
#                     print(f"✅ Appended to existing month in OPE_data")
#                     break
            
#             if not month_exists:
#                 await db["OPE_data"].update_one(
#                     {"employeeId": employee_code},
#                     {"$push": {"Data": {formatted_month_range: entries_to_submit}}}
#                 )
#                 print(f"✅ Added new month range to OPE_data")
        
#         # ✅ Add to PENDING collection
#         pending_doc = await db["Pending"].find_one({"ReportingEmpCode": reporting_manager_code})
        
#         if not pending_doc:
#             await db["Pending"].insert_one({
#                 "ReportingEmpCode": reporting_manager_code,
#                 "EmployeesCodes": [employee_code]
#             })
#             print(f"✅ Created NEW Pending document for manager {reporting_manager_code}")
#         else:
#             if employee_code not in pending_doc.get("EmployeesCodes", []):
#                 await db["Pending"].update_one(
#                     {"ReportingEmpCode": reporting_manager_code},
#                     {"$addToSet": {"EmployeesCodes": employee_code}}
#                 )
#                 print(f"✅ Added employee to Pending list")
        
#         # ✅ Delete from Temp_OPE_data
#         temp_data_array = temp_doc.get("Data", [])
        
#         for i, data_item in enumerate(temp_data_array):
#             if formatted_month_range in data_item:
#                 await db["Temp_OPE_data"].update_one(
#                     {"employeeId": employee_code},
#                     {"$pull": {"Data": {formatted_month_range: {"$exists": True}}}}
#                 )
#                 print(f"✅ Removed from Temp_OPE_data")
#                 break
        
#         # If no more temp data, delete document
#         updated_temp = await db["Temp_OPE_data"].find_one({"employeeId": employee_code})
#         if updated_temp and len(updated_temp.get("Data", [])) == 0:
#             await db["Temp_OPE_data"].delete_one({"employeeId": employee_code})
#             print(f"✅ Deleted empty Temp_OPE_data document")
        
#         print(f"\n✅✅ SUBMISSION COMPLETE ✅✅\n")
        
#         return {
#             "message": "Entries submitted successfully for approval",
#             "submitted_count": len(entries_to_submit),
#             "month_range": formatted_month_range,
#             "reporting_manager": reporting_manager_code,
#             "total_amount": total_amount,
#             "ope_label": ope_label,
#             "total_levels": total_levels,
#             "status": "pending_approval"
#         }
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         print(f"❌ Error submitting final: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))
            
# ✅ UPDATED: Submit final with dynamic approval levels based on limit
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
        
        # ✅ GET OPE LIMIT FROM EMPLOYEE DETAILS
        ope_limit = emp.get("OPE Limit", 5000)
        
        reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
        reporting_manager_name = emp.get("ReportingEmpName", "")
        partner = emp.get("Partner", "")
        
        if not reporting_manager_code:
            raise HTTPException(status_code=400, detail="No reporting manager assigned")
        
        print(f"👔 Reporting Manager: {reporting_manager_code} ({reporting_manager_name})")
        
        # ✅ CALCULATE TOTAL AMOUNT FOR THIS MONTH
        total_amount = sum(float(entry.get("amount", 0)) for entry in entries_to_submit)
        
        print(f"💰 Total amount: ₹{total_amount}")
        print(f"🎯 OPE Limit: ₹{ope_limit}")
        
        # ✅ DYNAMIC APPROVAL LEVELS BASED ON AMOUNT VS LIMIT
        if total_amount > ope_limit:
            ope_label = "Greater"
            total_levels = 3
            print(f"📊 Amount EXCEEDS limit → 3-level approval required")
        else:
            ope_label = "Less"
            total_levels = 2
            print(f"📊 Amount WITHIN limit → 2-level approval required")
        
        current_time = datetime.utcnow().isoformat()
        
        # ✅ CREATE OR UPDATE STATUS DOCUMENT (ONE PER EMPLOYEE)
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        # Create payroll entry with DYNAMIC levels
        payroll_entry = {
            "payroll_month": formatted_month_range,
            "ope_label": ope_label,
            "total_levels": total_levels,
            "limit": ope_limit,  # ✅ Use employee's actual limit
            "total_amount": total_amount,
            "L1": {
                "status": False,
                "approver_name": reporting_manager_name,
                "approver_code": reporting_manager_code,
                "approved_date": None,
                "level_name": "Reporting Manager"
            },
            "L2": {
                "status": False,
                "approver_name": "HR" if total_levels == 2 else partner,
                "approver_code": "",
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
                "approver_code": "",
                "approved_date": None,
                "level_name": "HR"
            }
            print(f"✅ Added L3 (HR) level for approval")
        
        if not status_doc:
            # ✅ CREATE NEW STATUS DOCUMENT
            new_status_doc = {
                "employeeId": employee_code,
                "employeeName": emp.get("Emp Name", ""),
                "approval_status": [payroll_entry]
            }
            result = await db["Status"].insert_one(new_status_doc)
            status_doc_id = str(result.inserted_id)
            print(f"✅ Created NEW Status document: {status_doc_id}")
        else:
            # ✅ UPDATE EXISTING STATUS DOCUMENT - ADD NEW PAYROLL MONTH
            status_doc_id = str(status_doc["_id"])
            
            # Check if this payroll month already exists
            approval_status = status_doc.get("approval_status", [])
            month_exists = False
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") == formatted_month_range:
                    # Update existing month
                    await db["Status"].update_one(
                        {"employeeId": employee_code},
                        {"$set": {f"approval_status.{i}": payroll_entry}}
                    )
                    month_exists = True
                    print(f"✅ Updated existing payroll month: {formatted_month_range}")
                    break
            
            if not month_exists:
                # Add new payroll month
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
        
        print(f"\n✅✅ SUBMISSION COMPLETE ✅✅")
        print(f"   Total Amount: ₹{total_amount}")
        print(f"   OPE Limit: ₹{ope_limit}")
        print(f"   Approval Levels: {total_levels}")
        print(f"   OPE Label: {ope_label}\n")
        
        return {
            "message": "Entries submitted successfully for approval",
            "submitted_count": len(entries_to_submit),
            "month_range": formatted_month_range,
            "reporting_manager": reporting_manager_code,
            "total_amount": total_amount,
            "ope_limit": ope_limit,  # ✅ Return limit in response
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
        payroll_months_approved = set()
        
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
                            f"Data.{i}.{month_range}.{j}.approver_name": manager_name
                        }}
                    )
                    
                    payroll_months_approved.add(month_range)
                    approved_count += 1
        
        if approved_count == 0:
            raise HTTPException(status_code=404, detail="No pending entries found")
        
        # ✅ UPDATE STATUS COLLECTION - UPDATE EACH PAYROLL MONTH
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_approved:
                    # Update L1 status
                    await db["Status"].update_one(
                        {"employeeId": employee_code},
                        {"$set": {
                            f"approval_status.{i}.L1.status": True,
                            f"approval_status.{i}.L1.approver_code": reporting_emp_code,
                            f"approval_status.{i}.L1.approver_name": manager_name,
                            f"approval_status.{i}.L1.approved_date": current_time,
                            f"approval_status.{i}.overall_status": "approved",
                            f"approval_status.{i}.current_level": "Completed"
                        }}
                    )
        
        # ✅ REMOVE FROM PENDING
        await db["Pending"].update_one(
            {"ReportingEmpCode": emp_reporting_manager_code},
            {"$pull": {"EmployeesCodes": employee_code}}
        )
        print(f"✅ Removed from Pending")
        
        # ✅ ADD TO APPROVED
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
            
# # ✅ UPDATED: Approve with multi-level support
# @app.post("/api/ope/manager/approve/{employee_code}")
# async def approve_employee_entries(
#     employee_code: str,
#     current_user=Depends(get_current_user)
# ):
#     try:
#         reporting_emp_code = current_user["employee_code"].strip().upper()
#         employee_code = employee_code.strip().upper()
        
#         print(f"\n{'='*60}")
#         print(f"✅ APPROVAL REQUEST")
#         print(f"Manager: {reporting_emp_code}")
#         print(f"Employee: {employee_code}")
#         print(f"{'='*60}\n")
        
#         # Get manager details
#         manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": reporting_emp_code})
#         if not manager:
#             raise HTTPException(status_code=403, detail="You are not a reporting manager")
        
#         manager_name = manager.get("ReportingEmpName", reporting_emp_code)
        
#         # Get employee details
#         emp = await db["Employee_details"].find_one({"EmpID": employee_code})
#         if not emp:
#             raise HTTPException(status_code=404, detail="Employee not found")
        
#         emp_reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
#         emp_partner = emp.get("Partner", "")
        
#         # ✅ DETERMINE CURRENT APPROVER'S LEVEL
#         approver_level = None
#         if reporting_emp_code == emp_reporting_manager_code:
#             approver_level = "L1"
#             print(f"👔 Approver is Reporting Manager (L1)")
#         elif manager_name == emp_partner or manager_name in emp_partner:
#             approver_level = "L2"
#             print(f"👔 Approver is Partner (L2)")
#         else:
#             # Could be HR or other approver
#             approver_level = "L3"
#             print(f"👔 Approver is HR or L3")
        
#         # Get OPE data
#         ope_doc = await db["OPE_data"].find_one({"employeeId": employee_code})
        
#         if not ope_doc:
#             raise HTTPException(status_code=404, detail="No OPE data found for employee")
        
#         approved_count = 0
#         current_time = datetime.utcnow().isoformat()
        
#         data_array = ope_doc.get("Data", [])
#         payroll_months_approved = set()
        
#         for i, data_item in enumerate(data_array):
#             for month_range, entries in data_item.items():
#                 for j, entry in enumerate(entries):
#                     entry_status = entry.get("status", "").lower()
                    
#                     if entry_status != "pending":
#                         continue
                    
#                     # ✅ APPROVE THIS ENTRY
#                     await db["OPE_data"].update_one(
#                         {"employeeId": employee_code},
#                         {"$set": {
#                             f"Data.{i}.{month_range}.{j}.status": "approved",
#                             f"Data.{i}.{month_range}.{j}.approved_date": current_time,
#                             f"Data.{i}.{month_range}.{j}.approved_by": reporting_emp_code,
#                             f"Data.{i}.{month_range}.{j}.approver_name": manager_name,
#                             f"Data.{i}.{month_range}.{j}.approver_level": approver_level  # ✅ NEW
#                         }}
#                     )
                    
#                     payroll_months_approved.add(month_range)
#                     approved_count += 1
        
#         if approved_count == 0:
#             raise HTTPException(status_code=404, detail="No pending entries found")
        
#         # ✅ UPDATE STATUS COLLECTION - MARK CURRENT LEVEL AS APPROVED
#         status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
#         if status_doc:
#             approval_status = status_doc.get("approval_status", [])
            
#             for i, ps in enumerate(approval_status):
#                 if ps.get("payroll_month") in payroll_months_approved:
#                     total_levels = ps.get("total_levels", 2)
                    
#                     print(f"📊 Payroll Month: {ps.get('payroll_month')}")
#                     print(f"   Total Levels: {total_levels}")
#                     print(f"   Approving at: {approver_level}")
                    
#                     # ✅ UPDATE CURRENT LEVEL
#                     await db["Status"].update_one(
#                         {"employeeId": employee_code},
#                         {"$set": {
#                             f"approval_status.{i}.{approver_level}.status": True,
#                             f"approval_status.{i}.{approver_level}.approver_code": reporting_emp_code,
#                             f"approval_status.{i}.{approver_level}.approver_name": manager_name,
#                             f"approval_status.{i}.{approver_level}.approved_date": current_time
#                         }}
#                     )
                    
#                     # ✅ CHECK IF ALL LEVELS APPROVED
#                     L1_status = ps.get("L1", {}).get("status", False) or (approver_level == "L1")
#                     L2_status = ps.get("L2", {}).get("status", False) or (approver_level == "L2")
                    
#                     # L3 status only relevant if total_levels = 3
#                     if total_levels == 3:
#                         L3_status = ps.get("L3", {}).get("status", False) or (approver_level == "L3")
#                     else:
#                         L3_status = True  # Consider as approved if not required
                    
#                     print(f"   L1: {L1_status}, L2: {L2_status}, L3: {L3_status}")
                    
#                     # ✅ DETERMINE NEXT LEVEL OR COMPLETION
#                     if total_levels == 2:
#                         if L1_status and L2_status:
#                             # ✅ FULLY APPROVED (2 levels)
#                             await db["Status"].update_one(
#                                 {"employeeId": employee_code},
#                                 {"$set": {
#                                     f"approval_status.{i}.overall_status": "approved",
#                                     f"approval_status.{i}.current_level": "Completed"
#                                 }}
#                             )
#                             print(f"   ✅ FULLY APPROVED (2 levels)")
#                         elif L1_status and not L2_status:
#                             # Move to L2
#                             await db["Status"].update_one(
#                                 {"employeeId": employee_code},
#                                 {"$set": {
#                                     f"approval_status.{i}.current_level": "L2"
#                                 }}
#                             )
#                             print(f"   ⏭️ Moving to L2 (HR)")
                    
#                     elif total_levels == 3:
#                         if L1_status and L2_status and L3_status:
#                             # ✅ FULLY APPROVED (3 levels)
#                             await db["Status"].update_one(
#                                 {"employeeId": employee_code},
#                                 {"$set": {
#                                     f"approval_status.{i}.overall_status": "approved",
#                                     f"approval_status.{i}.current_level": "Completed"
#                                 }}
#                             )
#                             print(f"   ✅ FULLY APPROVED (3 levels)")
#                         elif L1_status and L2_status and not L3_status:
#                             # Move to L3
#                             await db["Status"].update_one(
#                                 {"employeeId": employee_code},
#                                 {"$set": {
#                                     f"approval_status.{i}.current_level": "L3"
#                                 }}
#                             )
#                             print(f"   ⏭️ Moving to L3 (HR)")
#                         elif L1_status and not L2_status:
#                             # Move to L2
#                             await db["Status"].update_one(
#                                 {"employeeId": employee_code},
#                                 {"$set": {
#                                     f"approval_status.{i}.current_level": "L2"
#                                 }}
#                             )
#                             print(f"   ⏭️ Moving to L2 (Partner)")
        
#         # ✅ UPDATE PENDING/APPROVED COLLECTIONS ONLY IF FULLY APPROVED
#         # Check if employee is fully approved for ALL submitted months
#         all_completed = True
#         if status_doc:
#             for ps in status_doc.get("approval_status", []):
#                 if ps.get("overall_status") != "approved":
#                     all_completed = False
#                     break
        
#         if all_completed:
#             print(f"🎉 ALL payroll months FULLY APPROVED - Moving collections")
            
#             # ✅ REMOVE FROM PENDING
#             await db["Pending"].update_one(
#                 {"ReportingEmpCode": emp_reporting_manager_code},
#                 {"$pull": {"EmployeesCodes": employee_code}}
#             )
#             print(f"✅ Removed from Pending")
            
#             # ✅ ADD TO APPROVED
#             approved_doc = await db["Approved"].find_one({"ReportingEmpCode": reporting_emp_code})
#             if not approved_doc:
#                 await db["Approved"].insert_one({
#                     "ReportingEmpCode": reporting_emp_code,
#                     "EmployeesCodes": [employee_code]
#                 })
#                 print(f"✅ Created NEW Approved document")
#             else:
#                 if employee_code not in approved_doc.get("EmployeesCodes", []):
#                     await db["Approved"].update_one(
#                         {"ReportingEmpCode": reporting_emp_code},
#                         {"$addToSet": {"EmployeesCodes": employee_code}}
#                     )
#                     print(f"✅ Added to Approved collection")
#         else:
#             print(f"⏳ Still pending further approvals - NOT moving collections")
        
#         print(f"{'='*60}\n")
        
#         return {
#             "message": f"Approved {approved_count} entries at {approver_level}",
#             "approved_count": approved_count,
#             "employee_code": employee_code,
#             "approver_level": approver_level,
#             "all_completed": all_completed
#         }
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         print(f"\n❌❌ ERROR:")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


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
        
        # ✅ CHECK IF USER IS HR
        is_hr = (reporting_emp_code == "JHS729")
        
        # Verify manager (if not HR)
        manager_name = "HR"
        if not is_hr:
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
                                f"Data.{i}.{month_range}.{j}.rejector_name": manager_name,
                                f"Data.{i}.{month_range}.{j}.rejected_date": current_time,
                                f"Data.{i}.{month_range}.{j}.rejection_reason": reason
                            }}
                        )
                        
                        # Update Status collection
                        status_id = entry.get("status_id")
                        if status_id:
                            rejection_level = "L3" if is_hr else "L1"
                            
                            await db["Status"].update_one(
                                {"_id": ObjectId(status_id)},
                                {"$set": {
                                    "overall_status": "rejected",
                                    f"{rejection_level}.status": False,
                                    f"{rejection_level}.rejected_by": reporting_emp_code,
                                    f"{rejection_level}.rejected_date": current_time
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
            if is_hr:
                await db["Approved"].update_many(
                    {},
                    {"$pull": {"EmployeesCodes": employee_id}}
                )
            else:
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
        
        # ✅ CHECK IF USER IS HR
        is_hr = (reporting_emp_code == "JHS729")
        
        # Verify manager (if not HR)
        manager_name = "HR"
        if not is_hr:
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
                                f"Data.{i}.{month_range}.{j}.approver_name": manager_name,
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
                            approval_level = "L3" if is_hr else "L1"
                            
                            await db["Status"].update_one(
                                {"_id": ObjectId(status_id)},
                                {"$set": {
                                    "overall_status": "approved",
                                    f"{approval_level}.status": True,
                                    f"{approval_level}.approver_code": reporting_emp_code,
                                    f"{approval_level}.approver_name": manager_name,
                                    f"{approval_level}.approved_date": current_time,
                                    f"{approval_level}.rejected_by": None,
                                    f"{approval_level}.rejected_date": None
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
    HR approval (final level)
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
                    
                    # ✅ HR approves entries that are already approved by L1/L2
                    if entry_status == "approved":
                        # Mark as HR approved (no status change, just add HR approval)
                        await db["OPE_data"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"Data.{i}.{month_range}.{j}.hr_approved": True,
                                f"Data.{i}.{month_range}.{j}.hr_approved_by": hr_emp_code,
                                f"Data.{i}.{month_range}.{j}.hr_approved_date": current_time
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
                    
                    # ✅ UPDATE L2 OR L3 (depending on total_levels)
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
    HR rejection (final level)
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
        
        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):
                    entry_status = entry.get("status", "").lower()
                    
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
                                f"Data.{i}.{month_range}.{j}.rejected_level": "L2" if entry.get("total_levels", 2) == 2 else "L3"
                            }}
                        )
                        
                        rejected_count += 1
        
        if rejected_count == 0:
            raise HTTPException(status_code=404, detail="No entries found for HR rejection")
        
        # ✅ UPDATE STATUS COLLECTION
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
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
        
        # ✅ Find all Status documents where HR has approved
        status_docs = await db["Status"].find({
            "$or": [
                {"approval_status.L2.approver_code": hr_emp_code},
                {"approval_status.L3.approver_code": hr_emp_code}
            ]
        }).to_list(length=None)
        
        employee_codes = []
        for status_doc in status_docs:
            emp_id = status_doc.get("employeeId")
            if emp_id and emp_id not in employee_codes:
                # ✅ Check if at least one payroll month is fully approved by HR
                approval_status = status_doc.get("approval_status", [])
                has_hr_approval = False
                
                for ps in approval_status:
                    total_levels = ps.get("total_levels", 2)
                    
                    if total_levels == 2:
                        if ps.get("L2", {}).get("approver_code") == hr_emp_code:
                            has_hr_approval = True
                            break
                    elif total_levels == 3:
                        if ps.get("L3", {}).get("approver_code") == hr_emp_code:
                            has_hr_approval = True
                            break
                
                if has_hr_approval:
                    employee_codes.append(emp_id)
        
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
        
        # ✅ Find all OPE_data documents where HR has rejected
        ope_docs = await db["OPE_data"].find({}).to_list(length=None)
        
        employee_codes = []
        for ope_doc in ope_docs:
            emp_id = ope_doc.get("employeeId")
            data_array = ope_doc.get("Data", [])
            
            has_hr_rejection = False
            
            for data_item in data_array:
                for month_range, entries in data_item.items():
                    for entry in entries:
                        if (entry.get("status") == "rejected" and 
                            entry.get("rejected_by") == hr_emp_code):
                            has_hr_rejection = True
                            break
                if has_hr_rejection:
                    break
            
            if has_hr_rejection and emp_id not in employee_codes:
                employee_codes.append(emp_id)
        
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
    
# ---------- Serve static HTML ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")



