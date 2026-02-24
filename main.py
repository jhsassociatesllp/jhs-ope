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

# ── CHECK ADMIN ──────────────────────────────────────────────
@app.get("/api/check-admin/{employee_code}")
async def check_if_admin(employee_code: str, current_user=Depends(get_current_user)):
    """
    Check if the logged-in employee exists in the Admin collection's employee_codes array.
    """
    try:
        emp_code = employee_code.strip().upper()

        # Only allow users to check their own role
        if current_user["employee_code"].strip().upper() != emp_code:
            raise HTTPException(status_code=403, detail="Access denied")

        admin_doc = await db["Admin"].find_one(
            {"employee_codes": {"$in": [emp_code]}}
        )

        is_admin = admin_doc is not None
        print(f"{'✅' if is_admin else '❌'} Admin check for {emp_code}: {is_admin}")

        return {
            "employee_code": emp_code,
            "is_admin": is_admin
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error checking admin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ── ADMIN DASHBOARD DATA ─────────────────────────────────────
@app.get("/api/admin/dashboard")
async def admin_dashboard(
    payroll_month: Optional[str] = None,
    emp_name: Optional[str] = None,
    emp_id: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    try:
        admin_code = current_user["employee_code"].strip().upper()

        # Verify admin
        admin_doc = await db["Admin"].find_one({"employee_codes": {"$in": [admin_code]}})
        if not admin_doc:
            raise HTTPException(status_code=403, detail="Admin access required")

        # ── BUILD MATCH STAGE (Status collection) ────────────
        match_stage: dict = {}
        if emp_name:
            match_stage["employeeName"] = {"$regex": emp_name, "$options": "i"}
        if emp_id:
            match_stage["employeeId"] = {"$regex": emp_id, "$options": "i"}

        # ── BASE PIPELINE (unwind approval_status) ───────────
        base_pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {"$unwind": "$approval_status"},
        ]
        if payroll_month:
            base_pipeline.append(
                {"$match": {"approval_status.payroll_month": payroll_month}}
            )

        # ── KPI PIPELINE ─────────────────────────────────────
        kpi_pipeline = [
            *base_pipeline,
            {
                "$group": {
                    "_id": None,
                    "unique_employees": {"$addToSet": "$employeeId"},
                    "total_amount":     {"$sum": "$approval_status.total_amount"},
                    "count_3_level": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$approval_status.total_levels", 3]}, 1, 0
                            ]
                        }
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "total_employees":      {"$size": "$unique_employees"},
                    "total_amount":         {"$round": ["$total_amount", 2]},
                    "total_amount_greater": "$count_3_level"
                }
            }
        ]

        kpi_raw = await db["Status"].aggregate(kpi_pipeline).to_list(length=1)
        kpis = {"total_employees": 0, "total_amount": 0.0, "total_amount_greater": 0}
        if kpi_raw:
            kpis = kpi_raw[0]

        # ── PAYROLL DIFFERENCE KPI ────────────────────────────
        # Compare current month vs previous month total claims
        all_months_diff_pipeline = [
            {"$unwind": "$approval_status"},
            {
                "$group": {
                    "_id":   "$approval_status.payroll_month",
                    "total": {"$sum": "$approval_status.total_amount"}
                }
            },
            {"$sort": {"_id": -1}}   # latest month first
        ]
        months_diff_raw = await db["Status"].aggregate(all_months_diff_pipeline).to_list(length=None)

        payroll_diff_kpi = {
            "current_month":   None,
            "current_amount":  0.0,
            "previous_month":  None,
            "previous_amount": 0.0,
            "difference":      0.0,
            "direction":       "same"   # "up", "down", "same"
        }

        if payroll_month:
            # Filter selected: compare selected month vs previous month in DB
            all_sorted_months = [m["_id"] for m in months_diff_raw if m.get("_id")]
            if payroll_month in all_sorted_months:
                idx           = all_sorted_months.index(payroll_month)
                selected_amt  = next(
                    (m["total"] for m in months_diff_raw if m["_id"] == payroll_month), 0.0
                )
                prev_month    = all_sorted_months[idx + 1] if idx + 1 < len(all_sorted_months) else None
                prev_amt      = next(
                    (m["total"] for m in months_diff_raw if m["_id"] == prev_month), 0.0
                ) if prev_month else 0.0

                diff = round(selected_amt - prev_amt, 2)
                payroll_diff_kpi = {
                    "current_month":   payroll_month,
                    "current_amount":  round(selected_amt, 2),
                    "previous_month":  prev_month,
                    "previous_amount": round(prev_amt, 2),
                    "difference":      round(abs(diff), 2),
                    "direction":       "up" if diff > 0 else ("down" if diff < 0 else "same")
                }
        else:
            # No filter: compare latest 2 months in DB
            if len(months_diff_raw) >= 2:
                curr = months_diff_raw[0]
                prev = months_diff_raw[1]
                diff = round(curr["total"] - prev["total"], 2)
                payroll_diff_kpi = {
                    "current_month":   curr["_id"],
                    "current_amount":  round(curr["total"], 2),
                    "previous_month":  prev["_id"],
                    "previous_amount": round(prev["total"], 2),
                    "difference":      round(abs(diff), 2),
                    "direction":       "up" if diff > 0 else ("down" if diff < 0 else "same")
                }
            elif len(months_diff_raw) == 1:
                curr = months_diff_raw[0]
                payroll_diff_kpi["current_month"]  = curr["_id"]
                payroll_diff_kpi["current_amount"] = round(curr["total"], 2)

        # ── PARTNER-WISE CHART (from OPE_data.partner directly) ──
        # OPE_data has `partner` field with actual name e.g. "Huzefa Kaka"
        ope_match: dict = {}
        if emp_name:
            ope_match["employeeName"] = {"$regex": emp_name, "$options": "i"}
        if emp_id:
            ope_match["employeeId"] = {"$regex": emp_id, "$options": "i"}

        partner_pipeline = []
        if ope_match:
            partner_pipeline.append({"$match": ope_match})

        partner_pipeline += [
            {"$unwind": "$Data"},
            {"$addFields": {"dataKV": {"$objectToArray": "$Data"}}},
            {"$unwind": "$dataKV"},
        ]
        if payroll_month:
            partner_pipeline.append({"$match": {"dataKV.k": payroll_month}})

        partner_pipeline += [
            {"$unwind": "$dataKV.v"},
            # First group: per employee per partner (avoid double counting)
            {
                "$group": {
                    "_id": {
                        "partner":    "$partner",
                        "employeeId": "$employeeId"
                    },
                    "total": {"$sum": "$dataKV.v.amount"}
                }
            },
            # Then group by partner only
            {
                "$group": {
                    "_id":   "$_id.partner",
                    "total": {"$sum": "$total"}
                }
            },
            {"$match": {"_id": {"$nin": [None, "", "null"]}}},
            {"$sort":  {"total": -1}}
            # No $limit — show ALL partners
        ]

        partner_raw  = await db["OPE_data"].aggregate(partner_pipeline).to_list(length=None)
        partner_data = [
            {"_id": d.get("_id") or "Unknown", "total": round(d.get("total", 0), 2)}
            for d in partner_raw
        ]

        # ── PAYROLL-WISE CHART (from Status) ─────────────────
        payroll_pipeline = [
            *base_pipeline,
            {
                "$group": {
                    "_id":   "$approval_status.payroll_month",
                    "total": {"$sum": "$approval_status.total_amount"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        payroll_data = await db["Status"].aggregate(payroll_pipeline).to_list(length=None)
        payroll_data = [
            {"_id": d.get("_id") or "Unknown", "total": round(d.get("total", 0), 2)}
            for d in payroll_data
        ]

        # ── TOP 10 CLIENT-WISE CHART (from OPE_data) ─────────
        client_pipeline_stages = []
        if ope_match:
            client_pipeline_stages.append({"$match": ope_match})

        client_pipeline_stages += [
            {"$unwind": "$Data"},
            {"$addFields": {"dataKV": {"$objectToArray": "$Data"}}},
            {"$unwind": "$dataKV"},
        ]
        if payroll_month:
            client_pipeline_stages.append({"$match": {"dataKV.k": payroll_month}})

        client_pipeline_stages += [
            {"$unwind": "$dataKV.v"},
            {
                "$group": {
                    "_id":   "$dataKV.v.client",
                    "total": {"$sum": "$dataKV.v.amount"}
                }
            },
            {"$match": {"_id": {"$nin": [None, "", "null", "N/A"]}}},
            {"$sort":  {"total": -1}},
            {"$limit": 10}
        ]

        client_raw  = await db["OPE_data"].aggregate(client_pipeline_stages).to_list(length=None)
        client_data = [
            {"_id": d.get("_id") or "Unknown", "total": round(d.get("total", 0), 2)}
            for d in client_raw
        ]

        # ── TABLE (from Status) ───────────────────────────────
        table_pipeline = [
            *base_pipeline,
            {
                "$project": {
                    "_id": 0,
                    "employee_id":    "$employeeId",
                    "employee_name":  "$employeeName",
                    "payroll_month":  "$approval_status.payroll_month",
                    "total_amount":   "$approval_status.total_amount",
                    "limit":          "$approval_status.limit",
                    "overall_status": "$approval_status.overall_status",
                    "current_level":  "$approval_status.current_level",
                    "total_levels":   "$approval_status.total_levels",
                    "ope_label":      "$approval_status.ope_label"
                }
            },
            {"$sort": {"payroll_month": 1, "employee_name": 1}}
        ]
        table_data = await db["Status"].aggregate(table_pipeline).to_list(length=None)
        for row in table_data:
            if "total_amount" in row:
                row["total_amount"] = round(row["total_amount"], 2)

        # ── ALL PAYROLL MONTHS (for dropdown) ─────────────────
        months_pipeline = [
            {"$unwind": "$approval_status"},
            {"$group":  {"_id": "$approval_status.payroll_month"}},
            {"$sort":   {"_id": 1}}
        ]
        months_raw = await db["Status"].aggregate(months_pipeline).to_list(length=None)
        all_months = [m["_id"] for m in months_raw if m.get("_id")]

        print(f"✅ Admin dashboard: {kpis['total_employees']} employees, "
              f"₹{kpis['total_amount']} total, "
              f"{kpis['total_amount_greater']} entries > limit, "
              f"{len(client_data)} clients, "
              f"{len(partner_data)} partners, {len(payroll_data)} months, "
              f"diff: {payroll_diff_kpi['direction']} ₹{payroll_diff_kpi['difference']}")

        return {
            "kpis": {
                **kpis,
                "payroll_diff": payroll_diff_kpi    # current vs previous month difference
            },
            "charts": {
                "partner_wise": partner_data,
                "payroll_wise": payroll_data,
                "client_wise":  client_data,
            },
            "table":              table_data,
            "all_payroll_months": all_months
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Admin dashboard error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
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
#     Get all employees with pending entries
#     - For Reporting Managers: Show entries where status = "pending"
#     - For HR (JHS729): Show entries where L1 is approved (or L1 + L2 for 3-level)
#     """
#     try:
#         current_emp_code = current_user["employee_code"].strip().upper()
        
#         print(f"\n{'='*60}")
#         print(f"🔍 PENDING REQUEST FROM: {current_emp_code}")
#         print(f"{'='*60}\n")
        
#         # ✅ CHECK IF USER IS HR
#         is_hr = (current_emp_code == "JHS729")
        
#         if is_hr:
#             print(f"👔 USER IS HR - Fetching L1/L2 approved entries")
            
#             # ✅ GET ALL STATUS DOCUMENTS WHERE CURRENT_LEVEL IS L2 OR L3
#             status_docs = await db["Status"].find({
#                 "$or": [
#                     {"approval_status.current_level": "L2"},
#                     {"approval_status.current_level": "L3"}
#                 ]
#             }).to_list(length=None)
            
#             print(f"📊 Found {len(status_docs)} employees with entries pending HR approval")
            
#             pending_employees = []
            
#             for status_doc in status_docs:
#                 employee_id = status_doc.get("employeeId")
#                 employee_name = status_doc.get("employeeName")
#                 approval_status = status_doc.get("approval_status", [])
                
#                 # Get OPE data for this employee
#                 ope_doc = await db["OPE_data"].find_one({"employeeId": employee_id})
                
#                 if not ope_doc:
#                     continue
                
#                 pending_entries = []
                
#                 # ✅ FILTER ENTRIES BASED ON APPROVAL STATUS
#                 for ps in approval_status:
#                     current_level = ps.get("current_level")
#                     payroll_month = ps.get("payroll_month")
#                     total_levels = ps.get("total_levels", 2)
                    
#                     # ✅ HR should see entries where:
#                     # - For 2-level: current_level = "L2" and L1.status = True
#                     # - For 3-level: current_level = "L3" and L1.status = True and L2.status = True
                    
#                     L1_approved = ps.get("L1", {}).get("status", False)
#                     L2_approved = ps.get("L2", {}).get("status", False) if total_levels == 3 else True
                    
#                     should_show = False
                    
#                     if total_levels == 2 and current_level == "L2" and L1_approved:
#                         should_show = True
#                     elif total_levels == 3 and current_level == "L3" and L1_approved and L2_approved:
#                         should_show = True
                    
#                     if should_show:
#                         # Find entries for this payroll month
#                         data_array = ope_doc.get("Data", [])
                        
#                         for data_item in data_array:
#                             if payroll_month in data_item:
#                                 entries = data_item[payroll_month]
                                
#                                 for entry in entries:
#                                     # ✅ Only show entries with status "approved" (by L1/L2)
#                                     if entry.get("status", "").lower() == "approved":
#                                         pending_entries.append({
#                                             "_id": str(entry.get("_id", "")),
#                                             "month_range": payroll_month,
#                                             "date": entry.get("date"),
#                                             "client": entry.get("client"),
#                                             "project_id": entry.get("project_id"),
#                                             "project_name": entry.get("project_name"),
#                                             "project_type": entry.get("project_type", "N/A"),
#                                             "location_from": entry.get("location_from"),
#                                             "location_to": entry.get("location_to"),
#                                             "travel_mode": entry.get("travel_mode"),
#                                             "amount": entry.get("amount"),
#                                             "remarks": entry.get("remarks"),
#                                             "ticket_pdf": entry.get("ticket_pdf"),
#                                             "total_levels": total_levels,
#                                             "current_level": current_level
#                                         })
                
#                 if pending_entries:
#                     pending_employees.append({
#                         "employeeId": employee_id,
#                         "employeeName": employee_name,
#                         "designation": ope_doc.get("designation", ""),
#                         "pendingCount": len(pending_entries),
#                         "entries": pending_entries
#                     })
            
#             print(f"✅ Returning {len(pending_employees)} employees for HR")
            
#             return {
#                 "reporting_manager": current_emp_code,
#                 "is_hr": True,
#                 "total_employees": len(pending_employees),
#                 "employees": pending_employees
#             }
        
#         else:
#             # ✅ ORIGINAL LOGIC FOR REPORTING MANAGERS
#             print(f"👔 USER IS REPORTING MANAGER")
            
#             # Verify user is a manager
#             manager = await db["Reporting_managers"].find_one({"ReportingEmpCode": current_emp_code})
#             if not manager:
#                 raise HTTPException(status_code=403, detail="You are not a reporting manager")
            
#             # Get all employees under this manager
#             employees = await db["Employee_details"].find(
#                 {"ReportingEmpCode": current_emp_code}
#             ).to_list(length=None)
            
#             print(f"👥 Found {len(employees)} employees under manager")
            
#             pending_employees = []
            
#             for emp in employees:
#                 emp_code = emp.get("EmpID")
#                 emp_name = emp.get("Emp Name")
                
#                 # Get OPE data
#                 ope_doc = await db["OPE_data"].find_one({"employeeId": emp_code})
                
#                 if ope_doc:
#                     pending_entries = []
#                     data_array = ope_doc.get("Data", [])
                    
#                     for data_item in data_array:
#                         for month_range, entries in data_item.items():
#                             for entry in entries:
#                                 entry_status = entry.get("status", "pending").lower()
#                                 if entry_status == "pending":
#                                     pending_entries.append({
#                                         "_id": str(entry.get("_id", "")),
#                                         "month_range": month_range,
#                                         "date": entry.get("date"),
#                                         "client": entry.get("client"),
#                                         "project_id": entry.get("project_id"),
#                                         "project_name": entry.get("project_name"),
#                                         "project_type": entry.get("project_type", "N/A"),
#                                         "location_from": entry.get("location_from"),
#                                         "location_to": entry.get("location_to"),
#                                         "travel_mode": entry.get("travel_mode"),
#                                         "amount": entry.get("amount"),
#                                         "remarks": entry.get("remarks"),
#                                         "ticket_pdf": entry.get("ticket_pdf")
#                                     })
                    
#                     if pending_entries:
#                         pending_employees.append({
#                             "employeeId": emp_code,
#                             "employeeName": emp_name,
#                             "designation": emp.get("Designation Name", ""),
#                             "pendingCount": len(pending_entries),
#                             "entries": pending_entries
#                         })
            
#             print(f"✅ Returning {len(pending_employees)} employees for manager")
            
#             return {
#                 "reporting_manager": current_emp_code,
#                 "is_hr": False,
#                 "total_employees": len(pending_employees),
#                 "employees": pending_employees
#             }
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         print(f"❌ Error: {str(e)}")
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
# SUBMIT FINAL - Move from Temp_OPE_data to OPE_data
# ============================================
            
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
        
        # ✅ GET OPE LIMIT FROM EMPLOYEE DETAILS
        ope_limit = emp.get("OPE Limit", 5000)
        
        reporting_manager_code = emp.get("ReportingEmpCode", "").strip().upper()
        reporting_manager_name = emp.get("ReportingEmpName", "")
        partner = emp.get("Partner", "")
        
        if not reporting_manager_code:
            raise HTTPException(status_code=400, detail="No reporting manager assigned")
        
        print(f"👔 Reporting Manager: {reporting_manager_code} ({reporting_manager_name})")
        
        # ✅ CALCULATE TOTAL AMOUNT FOR NEW ENTRIES
        new_entries_amount = sum(float(entry.get("amount", 0)) for entry in entries_to_submit)
        
        print(f"💰 New entries amount: ₹{new_entries_amount}")
        print(f"🎯 OPE Limit: ₹{ope_limit}")
        
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
            print(f"📊 Cumulative amount EXCEEDS limit → 3-level approval required")
        else:
            ope_label = "Less"
            total_levels = 2
            print(f"📊 Cumulative amount WITHIN limit → 2-level approval required")
        
        current_time = datetime.utcnow().isoformat()
        
        # ✅ CREATE PAYROLL ENTRY WITH CUMULATIVE TOTAL
        payroll_entry = {
            "payroll_month": formatted_month_range,
            "ope_label": ope_label,
            "total_levels": total_levels,
            "limit": ope_limit,
            "total_amount": cumulative_total,  # ✅ CUMULATIVE TOTAL
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
        
        # ✅ CREATE OR UPDATE STATUS DOCUMENT
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
            # ✅ UPDATE EXISTING STATUS DOCUMENT
            status_doc_id = str(status_doc["_id"])
            
            if month_exists:
                # ✅ UPDATE EXISTING MONTH WITH CUMULATIVE TOTAL
                print(f"🔄 Updating existing month entry at index {existing_month_index}")
                
                update_fields = {
                    f"approval_status.{existing_month_index}.total_amount": cumulative_total,
                    f"approval_status.{existing_month_index}.ope_label": ope_label,
                    f"approval_status.{existing_month_index}.total_levels": total_levels,
                    f"approval_status.{existing_month_index}.submission_date": current_time
                }
                
                # ✅ Add L3 if total_levels changed from 2 to 3
                if total_levels == 3:
                    update_fields[f"approval_status.{existing_month_index}.L3"] = {
                        "status": False,
                        "approver_name": "HR",
                        "approver_code": "",
                        "approved_date": None,
                        "level_name": "HR"
                    }
                    update_fields[f"approval_status.{existing_month_index}.L2.approver_name"] = partner
                    update_fields[f"approval_status.{existing_month_index}.L2.level_name"] = "Partner"
                
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
        print(f"   Previous Total: ₹{existing_total}")
        print(f"   New Entries: +₹{new_entries_amount}")
        print(f"   Cumulative Total: ₹{cumulative_total}")
        print(f"   OPE Limit: ₹{ope_limit}")
        print(f"   Approval Levels: {total_levels}")
        print(f"   OPE Label: {ope_label}")
        print(f"{'='*60}\n")
        
        return {
            "message": "Entries submitted successfully for approval",
            "submitted_count": len(entries_to_submit),
            "month_range": formatted_month_range,
            "reporting_manager": reporting_manager_code,
            "previous_total": existing_total,  # ✅ NEW
            "new_entries_amount": new_entries_amount,  # ✅ NEW
            "total_amount": cumulative_total,  # ✅ CHANGED TO CUMULATIVE
            "ope_limit": ope_limit,
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
        
        # ✅ UPDATE STATUS COLLECTION
        status_doc = await db["Status"].find_one({"employeeId": employee_code})
        
        if status_doc:
            approval_status = status_doc.get("approval_status", [])
            
            for i, ps in enumerate(approval_status):
                if ps.get("payroll_month") in payroll_months_approved:
                    total_levels = ps.get("total_levels", 2)
                    
                    # ✅ CRITICAL FIX: Update L1 and set NEXT level
                    if total_levels == 2:
                        # 2-level approval: L1 done, now pending at L2 (HR)
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L1.status": True,
                                f"approval_status.{i}.L1.approver_code": reporting_emp_code,
                                f"approval_status.{i}.L1.approver_name": manager_name,
                                f"approval_status.{i}.L1.approved_date": current_time,
                                f"approval_status.{i}.overall_status": "pending",  # ✅ CHANGED
                                f"approval_status.{i}.current_level": "L2"  # ✅ CHANGED
                            }}
                        )
                        print(f"✅ 2-level: L1 approved, now pending at L2 (HR)")
                        
                    elif total_levels == 3:
                        # 3-level approval: L1 done, now pending at L2 (Partner)
                        await db["Status"].update_one(
                            {"employeeId": employee_code},
                            {"$set": {
                                f"approval_status.{i}.L1.status": True,
                                f"approval_status.{i}.L1.approver_code": reporting_emp_code,
                                f"approval_status.{i}.L1.approver_name": manager_name,
                                f"approval_status.{i}.L1.approved_date": current_time,
                                f"approval_status.{i}.overall_status": "pending",  # ✅ CHANGED
                                f"approval_status.{i}.current_level": "L2"  # ✅ CHANGED
                            }}
                        )
                        print(f"✅ 3-level: L1 approved, now pending at L2 (Partner)")
        
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
        
        print(f"\n✅✅ APPROVAL COMPLETE")
        print(f"   Total approved: {approved_count}")
        print(f"   Status: Pending at next level")
        print(f"{'='*60}\n")
        
        return {
            "message": f"Approved {approved_count} entries",
            "approved_count": approved_count,
            "employee_code": employee_code,
            "next_level": "L2"
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
        

@app.get("/api/admin/export/client-wise")
async def export_client_wise_excel(
    payroll_month: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    try:
        admin_code = current_user["employee_code"].strip().upper()
        admin_doc = await db["Admin"].find_one({"employee_codes": {"$in": [admin_code]}})
        if not admin_doc:
            raise HTTPException(status_code=403, detail="Admin access required")

        # ── AGGREGATE: client → employees → amounts ──────────
        pipeline = [
            {"$unwind": "$Data"},
            {"$addFields": {"dataKV": {"$objectToArray": "$Data"}}},
            {"$unwind": "$dataKV"},
        ]
        if payroll_month:
            pipeline.append({"$match": {"dataKV.k": payroll_month}})

        pipeline += [
            {"$unwind": "$dataKV.v"},
            {"$match": {"dataKV.v.client": {"$nin": [None, "", "null", "N/A"]}}},
            {
                "$group": {
                    "_id": {
                        "client":     "$dataKV.v.client",
                        "employeeId": "$employeeId",
                        "empName":    "$employeeName"
                    },
                    "total_amount": {"$sum": "$dataKV.v.amount"}
                }
            },
            {
                "$group": {
                    "_id":   "$_id.client",
                    "total_claim": {"$sum": "$total_amount"},
                    "employees": {
                        "$push": {
                            "employee_id":   "$_id.employeeId",
                            "employee_name": "$_id.empName",
                            "amount":        "$total_amount"
                        }
                    }
                }
            },
            {"$sort": {"total_claim": -1}}
        ]

        raw = await db["OPE_data"].aggregate(pipeline).to_list(length=None)

        if not raw:
            raise HTTPException(status_code=404, detail="No data found")

        # ── BUILD EXCEL WITH openpyxl ─────────────────────────
        import io
        from openpyxl import Workbook
        from openpyxl.styles import (
            Font, PatternFill, Alignment, Border, Side
        )
        from openpyxl.utils import get_column_letter

        wb = Workbook()

        # ── SHEET 1: Summary ──────────────────────────────────
        ws_summary = wb.active
        ws_summary.title = "Client Summary"

        # Header fill colors
        header_fill   = PatternFill("solid", start_color="F59E0B", end_color="F59E0B")
        subhead_fill  = PatternFill("solid", start_color="1E293B", end_color="1E293B")
        alt_fill      = PatternFill("solid", start_color="FFFBEB", end_color="FFFBEB")
        total_fill    = PatternFill("solid", start_color="D1FAE5", end_color="D1FAE5")
        thin_border   = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        # Title row
        ws_summary.merge_cells("A1:E1")
        title_cell = ws_summary["A1"]
        title_cell.value = f"Client-wise OPE Claims Report" + (f" — {payroll_month}" if payroll_month else " — All Months")
        title_cell.font      = Font(bold=True, size=14, color="FFFFFF", name="Arial")
        title_cell.fill      = subhead_fill
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws_summary.row_dimensions[1].height = 30

        # Column headers
        summary_headers = ["#", "Client Name", "Total Employees", "Total Claim (₹)", "Employee IDs"]
        for col, h in enumerate(summary_headers, 1):
            cell = ws_summary.cell(row=2, column=col, value=h)
            cell.font      = Font(bold=True, color="FFFFFF", name="Arial", size=11)
            cell.fill      = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border    = thin_border
        ws_summary.row_dimensions[2].height = 22

        # Data rows
        for idx, client_doc in enumerate(raw, 1):
            row   = idx + 2
            emps  = client_doc.get("employees", [])
            emp_ids = ", ".join(sorted(set(e["employee_id"] for e in emps)))

            fill = alt_fill if idx % 2 == 0 else PatternFill("solid", start_color="FFFFFF", end_color="FFFFFF")

            values = [
                idx,
                client_doc["_id"],
                len(emps),
                round(client_doc["total_claim"], 2),
                emp_ids
            ]
            for col, val in enumerate(values, 1):
                cell = ws_summary.cell(row=row, column=col, value=val)
                cell.font      = Font(name="Arial", size=10)
                cell.fill      = fill
                cell.border    = thin_border
                cell.alignment = Alignment(
                    horizontal="center" if col in [1, 3] else "left",
                    vertical="center",
                    wrap_text=(col == 5)
                )

        # Total row
        total_row = len(raw) + 3
        ws_summary.cell(total_row, 1, "TOTAL").font = Font(bold=True, name="Arial")
        ws_summary.cell(total_row, 1).fill = total_fill
        ws_summary.cell(total_row, 2, "All Clients").font = Font(bold=True, name="Arial")
        ws_summary.cell(total_row, 2).fill = total_fill
        total_emp = sum(len(d["employees"]) for d in raw)
        ws_summary.cell(total_row, 3, total_emp).font = Font(bold=True, name="Arial")
        ws_summary.cell(total_row, 3).fill = total_fill
        ws_summary.cell(total_row, 3).alignment = Alignment(horizontal="center")
        ws_summary.cell(total_row, 4, f'=SUM(D3:D{total_row-1})').font = Font(bold=True, name="Arial")
        ws_summary.cell(total_row, 4).fill = total_fill
        for c in range(1, 6):
            ws_summary.cell(total_row, c).border = thin_border

        # Column widths
        ws_summary.column_dimensions["A"].width = 6
        ws_summary.column_dimensions["B"].width = 30
        ws_summary.column_dimensions["C"].width = 18
        ws_summary.column_dimensions["D"].width = 20
        ws_summary.column_dimensions["E"].width = 60

        # ── SHEET 2: Employee Detail ──────────────────────────
        ws_detail = wb.create_sheet("Employee Detail")

        ws_detail.merge_cells("A1:E1")
        t2 = ws_detail["A1"]
        t2.value = f"Employee-wise Detail per Client" + (f" — {payroll_month}" if payroll_month else " — All Months")
        t2.font      = Font(bold=True, size=14, color="FFFFFF", name="Arial")
        t2.fill      = subhead_fill
        t2.alignment = Alignment(horizontal="center", vertical="center")
        ws_detail.row_dimensions[1].height = 30

        detail_headers = ["#", "Client Name", "Employee ID", "Employee Name", "Amount Claimed (₹)"]
        for col, h in enumerate(detail_headers, 1):
            cell = ws_detail.cell(row=2, column=col, value=h)
            cell.font      = Font(bold=True, color="FFFFFF", name="Arial", size=11)
            cell.fill      = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border    = thin_border
        ws_detail.row_dimensions[2].height = 22

        detail_row = 3
        sr_no = 1
        for client_doc in raw:
            client_name = client_doc["_id"]
            employees   = sorted(client_doc["employees"], key=lambda x: x["employee_id"])
            for emp in employees:
                fill = alt_fill if sr_no % 2 == 0 else PatternFill("solid", start_color="FFFFFF", end_color="FFFFFF")
                vals = [sr_no, client_name, emp["employee_id"], emp["employee_name"], round(emp["amount"], 2)]
                for col, val in enumerate(vals, 1):
                    cell = ws_detail.cell(row=detail_row, column=col, value=val)
                    cell.font      = Font(name="Arial", size=10)
                    cell.fill      = fill
                    cell.border    = thin_border
                    cell.alignment = Alignment(horizontal="center" if col in [1, 3] else "left", vertical="center")
                detail_row += 1
                sr_no      += 1

        ws_detail.column_dimensions["A"].width = 6
        ws_detail.column_dimensions["B"].width = 30
        ws_detail.column_dimensions["C"].width = 14
        ws_detail.column_dimensions["D"].width = 28
        ws_detail.column_dimensions["E"].width = 22

        # ── STREAM RESPONSE ──────────────────────────────────
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        from fastapi.responses import StreamingResponse
        filename = f"client_wise_claims{'_' + payroll_month.replace(' ', '_').replace('/', '-') if payroll_month else ''}.xlsx"

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Export error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/admin/export/partner-wise")
async def export_partner_wise_excel(
    payroll_month: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    try:
        admin_code = current_user["employee_code"].strip().upper()
        admin_doc = await db["Admin"].find_one({"employee_codes": {"$in": [admin_code]}})
        if not admin_doc:
            raise HTTPException(status_code=403, detail="Admin access required")

        # ── AGGREGATE: partner → employees → amounts ──────────
        pipeline = [
            {"$unwind": "$Data"},
            {"$addFields": {"dataKV": {"$objectToArray": "$Data"}}},
            {"$unwind": "$dataKV"},
        ]
        if payroll_month:
            pipeline.append({"$match": {"dataKV.k": payroll_month}})

        pipeline += [
            {"$unwind": "$dataKV.v"},
            {"$match": {"partner": {"$nin": [None, "", "null"]}}},
            {
                "$group": {
                    "_id": {
                        "partner":    "$partner",
                        "employeeId": "$employeeId",
                        "empName":    "$employeeName"
                    },
                    "total_amount": {"$sum": "$dataKV.v.amount"}
                }
            },
            {
                "$group": {
                    "_id":         "$_id.partner",
                    "total_claim": {"$sum": "$total_amount"},
                    "employees": {
                        "$push": {
                            "employee_id":   "$_id.employeeId",
                            "employee_name": "$_id.empName",
                            "amount":        "$total_amount"
                        }
                    }
                }
            },
            {"$sort": {"total_claim": -1}}
        ]

        raw = await db["OPE_data"].aggregate(pipeline).to_list(length=None)

        if not raw:
            raise HTTPException(status_code=404, detail="No data found")

        # ── BUILD EXCEL ───────────────────────────────────────
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = Workbook()

        header_fill  = PatternFill("solid", start_color="F59E0B", end_color="F59E0B")
        subhead_fill = PatternFill("solid", start_color="1E293B", end_color="1E293B")
        alt_fill     = PatternFill("solid", start_color="FFFBEB", end_color="FFFBEB")
        white_fill   = PatternFill("solid", start_color="FFFFFF", end_color="FFFFFF")
        total_fill   = PatternFill("solid", start_color="D1FAE5", end_color="D1FAE5")
        thin_border  = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        # ── SHEET 1: Partner Summary ──────────────────────────
        ws1 = wb.active
        ws1.title = "Partner Summary"

        ws1.merge_cells("A1:E1")
        t = ws1["A1"]
        t.value      = "Partner-wise OPE Claims Report" + (f" — {payroll_month}" if payroll_month else " — All Months")
        t.font       = Font(bold=True, size=14, color="FFFFFF", name="Arial")
        t.fill       = subhead_fill
        t.alignment  = Alignment(horizontal="center", vertical="center")
        ws1.row_dimensions[1].height = 30

        headers = ["#", "Partner Name", "Total Employees", "Total Claim (₹)", "Employee IDs"]
        for col, h in enumerate(headers, 1):
            cell = ws1.cell(row=2, column=col, value=h)
            cell.font      = Font(bold=True, color="FFFFFF", name="Arial", size=11)
            cell.fill      = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border    = thin_border
        ws1.row_dimensions[2].height = 22

        for idx, doc in enumerate(raw, 1):
            row     = idx + 2
            emps    = doc.get("employees", [])
            emp_ids = ", ".join(sorted(set(e["employee_id"] for e in emps)))
            fill    = alt_fill if idx % 2 == 0 else white_fill

            vals = [idx, doc["_id"], len(emps), round(doc["total_claim"], 2), emp_ids]
            for col, val in enumerate(vals, 1):
                cell = ws1.cell(row=row, column=col, value=val)
                cell.font      = Font(name="Arial", size=10)
                cell.fill      = fill
                cell.border    = thin_border
                cell.alignment = Alignment(
                    horizontal="center" if col in [1, 3] else "left",
                    vertical="center",
                    wrap_text=(col == 5)
                )

        # Total row
        tr = len(raw) + 3
        for c in range(1, 6):
            ws1.cell(tr, c).fill   = total_fill
            ws1.cell(tr, c).border = thin_border
            ws1.cell(tr, c).font   = Font(bold=True, name="Arial")
        ws1.cell(tr, 1, "TOTAL")
        ws1.cell(tr, 2, "All Partners")
        ws1.cell(tr, 3, sum(len(d["employees"]) for d in raw)).alignment = Alignment(horizontal="center")
        ws1.cell(tr, 4, f"=SUM(D3:D{tr-1})")

        ws1.column_dimensions["A"].width = 6
        ws1.column_dimensions["B"].width = 30
        ws1.column_dimensions["C"].width = 18
        ws1.column_dimensions["D"].width = 20
        ws1.column_dimensions["E"].width = 60

        # ── SHEET 2: Employee Detail ──────────────────────────
        ws2 = wb.create_sheet("Employee Detail")

        ws2.merge_cells("A1:E1")
        t2 = ws2["A1"]
        t2.value     = "Employee-wise Detail per Partner" + (f" — {payroll_month}" if payroll_month else " — All Months")
        t2.font      = Font(bold=True, size=14, color="FFFFFF", name="Arial")
        t2.fill      = subhead_fill
        t2.alignment = Alignment(horizontal="center", vertical="center")
        ws2.row_dimensions[1].height = 30

        det_headers = ["#", "Partner Name", "Employee ID", "Employee Name", "Amount Claimed (₹)"]
        for col, h in enumerate(det_headers, 1):
            cell = ws2.cell(row=2, column=col, value=h)
            cell.font      = Font(bold=True, color="FFFFFF", name="Arial", size=11)
            cell.fill      = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border    = thin_border
        ws2.row_dimensions[2].height = 22

        det_row = 3
        sr      = 1
        for doc in raw:
            for emp in sorted(doc["employees"], key=lambda x: x["employee_id"]):
                fill = alt_fill if sr % 2 == 0 else white_fill
                vals = [sr, doc["_id"], emp["employee_id"], emp["employee_name"], round(emp["amount"], 2)]
                for col, val in enumerate(vals, 1):
                    cell = ws2.cell(row=det_row, column=col, value=val)
                    cell.font      = Font(name="Arial", size=10)
                    cell.fill      = fill
                    cell.border    = thin_border
                    cell.alignment = Alignment(
                        horizontal="center" if col in [1, 3] else "left",
                        vertical="center"
                    )
                det_row += 1
                sr      += 1

        ws2.column_dimensions["A"].width = 6
        ws2.column_dimensions["B"].width = 30
        ws2.column_dimensions["C"].width = 14
        ws2.column_dimensions["D"].width = 28
        ws2.column_dimensions["E"].width = 22

        # ── STREAM ────────────────────────────────────────────
        import io
        from fastapi.responses import StreamingResponse

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        fname = f"partner_wise_claims{'_' + payroll_month.replace(' ', '_').replace('/', '-') if payroll_month else ''}.xlsx"

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'}
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Partner export error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
# ---------- Serve static HTML ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
