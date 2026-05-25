# """
# migrate_pdfs_to_gridfs.py
# ─────────────────────────
# One-time script to move all existing base64 PDF strings from
# OPE_data and Temp_OPE_data into MongoDB GridFS, then replace
# the base64 string with the resulting GridFS file_id.

# Run ONCE on the server, then discard.

# Usage:
#     pip install motor pymongo python-dotenv
#     python migrate_pdfs_to_gridfs.py
# """

# import asyncio
# import base64
# import io
# import os
# from datetime import datetime
# from bson import ObjectId
# from dotenv import load_dotenv
# from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

# load_dotenv()

# MONGO_URI = os.getenv("MONGO_URI")
# MONGO_DB  = os.getenv("MONGO_DB")


# def is_base64_pdf(value: str) -> bool:
#     """Return True if value looks like a base64-encoded PDF (not a GridFS ObjectId)."""
#     if not value or not isinstance(value, str):
#         return False
#     # GridFS ObjectId is exactly 24 hex characters
#     if len(value) == 24:
#         try:
#             ObjectId(value)
#             return False          # Already a GridFS ID — skip
#         except Exception:
#             pass
#     # If it's longer than 24 chars it's almost certainly base64
#     return len(value) > 24


# async def upload_to_gridfs(bucket, file_content: bytes, filename: str) -> str:
#     file_id = await bucket.upload_from_stream(filename, io.BytesIO(file_content))
#     return str(file_id)


# async def migrate_collection(db, collection_name: str):
#     """
#     Walk every document → Data array → month array → entry,
#     and migrate any base64 ticket_pdf to GridFS.
#     """
#     collection = db[collection_name]
#     bucket     = AsyncIOMotorGridFSBucket(db)

#     docs = await collection.find({}).to_list(length=None)
#     print(f"\n{'='*60}")
#     print(f"📂 {collection_name}: {len(docs)} documents")
#     print(f"{'='*60}")

#     total_migrated = 0
#     total_skipped  = 0
#     total_errors   = 0

#     for doc in docs:
#         emp_id     = doc.get("employeeId", str(doc["_id"]))
#         data_array = doc.get("Data", [])

#         for i, data_item in enumerate(data_array):
#             for month_range, entries in data_item.items():
#                 for j, entry in enumerate(entries):
#                     ticket_pdf = entry.get("ticket_pdf")

#                     if not ticket_pdf:
#                         total_skipped += 1
#                         continue

#                     if not is_base64_pdf(ticket_pdf):
#                         total_skipped += 1
#                         continue

#                     # Decode base64 → bytes
#                     try:
#                         pdf_bytes = base64.b64decode(ticket_pdf)
#                     except Exception as e:
#                         print(f"  ❌ Decode error [{emp_id} / {month_range} / {j}]: {e}")
#                         total_errors += 1
#                         continue

#                     # Upload to GridFS
#                     try:
#                         filename  = f"migrated_{collection_name}_{emp_id}_{i}_{j}.pdf"
#                         gridfs_id = await upload_to_gridfs(bucket, pdf_bytes, filename)
#                     except Exception as e:
#                         print(f"  ❌ GridFS upload error [{emp_id} / {month_range} / {j}]: {e}")
#                         total_errors += 1
#                         continue

#                     # Update MongoDB: replace base64 with GridFS ID
#                     try:
#                         await collection.update_one(
#                             {"_id": doc["_id"]},
#                             {"$set": {f"Data.{i}.{month_range}.{j}.ticket_pdf": gridfs_id}}
#                         )
#                         print(f"  ✅ Migrated [{emp_id} / {month_range} / entry {j}] → {gridfs_id}")
#                         total_migrated += 1
#                     except Exception as e:
#                         print(f"  ❌ Update error [{emp_id} / {month_range} / {j}]: {e}")
#                         total_errors += 1

#     print(f"\n📊 {collection_name} summary:")
#     print(f"   ✅ Migrated : {total_migrated}")
#     print(f"   ⏭️  Skipped  : {total_skipped} (already GridFS ID or no PDF)")
#     print(f"   ❌ Errors   : {total_errors}")
#     return total_migrated, total_errors


# async def main():
#     print(f"\n{'#'*60}")
#     print(f"# OPE PDF → GridFS Migration")
#     print(f"# Started: {datetime.utcnow().isoformat()}")
#     print(f"{'#'*60}")

#     client = AsyncIOMotorClient(MONGO_URI)
#     db     = client[MONGO_DB]
    
#     collections = await db.list_collection_names()
#     print("Collections in DB:", collections)

#     try:
#         # Migrate both collections
#         m1, e1 = await migrate_collection(db, "OPE_data")
#         m2, e2 = await migrate_collection(db, "Temp_OPE_data")

#         print(f"\n{'#'*60}")
#         print(f"# MIGRATION COMPLETE")
#         print(f"# Total migrated : {m1 + m2}")
#         print(f"# Total errors   : {e1 + e2}")
#         print(f"# Finished: {datetime.utcnow().isoformat()}")
#         print(f"{'#'*60}\n")

#         if e1 + e2 > 0:
#             print("⚠️  Some entries failed. Re-run the script — it safely skips already-migrated entries.")
#         else:
#             print("✅ All PDFs migrated successfully. You can now deploy the updated main.py.")

#     finally:
#         client.close()


# if __name__ == "__main__":
#     asyncio.run(main())



import asyncio
import base64
import io
import os
from datetime import datetime, UTC
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB  = os.getenv("MONGO_DB")

if not MONGO_URI or not MONGO_DB:
    raise ValueError("Missing MongoDB configuration")

def is_base64_pdf(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    if len(value) == 24:
        try:
            ObjectId(value)
            return False
        except:
            pass
    return len(value) > 100  # safer threshold


async def upload_to_gridfs(bucket, file_content: bytes, filename: str) -> str:
    return str(await bucket.upload_from_stream(filename, io.BytesIO(file_content)))


async def migrate_collection(db, collection_name: str):
    collection = db[collection_name]
    bucket     = AsyncIOMotorGridFSBucket(db)

    total_docs = await collection.count_documents({})
    print(f"\n📂 {collection_name}: {total_docs} documents")

    cursor = collection.find({}, batch_size=5)  # small batch = stable

    migrated = 0
    skipped  = 0
    errors   = 0
    processed_docs = 0

    async for doc in cursor:
        processed_docs += 1
        emp_id = doc.get("employeeId", str(doc["_id"]))
        data_array = doc.get("Data", [])

        for i, data_item in enumerate(data_array):
            for month_range, entries in data_item.items():
                for j, entry in enumerate(entries):

                    ticket_pdf = entry.get("ticket_pdf")

                    if not ticket_pdf or not is_base64_pdf(ticket_pdf):
                        skipped += 1
                        continue

                    # 🔹 Decode base64 safely
                    try:
                        pdf_bytes = base64.b64decode(ticket_pdf)
                    except Exception as e:
                        print(f"❌ Decode error [{emp_id}/{month_range}/{j}]: {e}")
                        errors += 1
                        continue

                    # 🔹 Upload to GridFS
                    try:
                        filename = f"{collection_name}_{emp_id}_{i}_{j}.pdf"
                        gridfs_id = await upload_to_gridfs(bucket, pdf_bytes, filename)
                    except Exception as e:
                        print(f"❌ Upload error [{emp_id}/{month_range}/{j}]: {e}")
                        errors += 1
                        continue

                    # 🔹 Update DB
                    try:
                        await collection.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {f"Data.{i}.{month_range}.{j}.ticket_pdf": gridfs_id}}
                        )
                        migrated += 1
                    except Exception as e:
                        print(f"❌ Update error [{emp_id}/{month_range}/{j}]: {e}")
                        errors += 1

        # 🔥 Progress logging (critical for long runs)
        if processed_docs % 10 == 0:
            print(f"➡️ Processed {processed_docs}/{total_docs} docs | Migrated: {migrated}")

    print(f"\n📊 {collection_name} DONE")
    print(f"   ✅ Migrated : {migrated}")
    print(f"   ⏭️ Skipped  : {skipped}")
    print(f"   ❌ Errors   : {errors}")

    return migrated, errors


async def main():
    print("\n" + "#"*60)
    print("# OPE PDF → GridFS Migration")
    print(f"# Started: {datetime.now(UTC).isoformat()}")
    print("#"*60)

    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]

    collections = await db.list_collection_names()
    print("Collections:", collections)

    try:
        m1, e1 = await migrate_collection(db, "OPE_data")
        m2, e2 = await migrate_collection(db, "Temp_OPE_data")

        print("\n" + "#"*60)
        print("# MIGRATION COMPLETE")
        print(f"# Total migrated : {m1 + m2}")
        print(f"# Total errors   : {e1 + e2}")
        print(f"# Finished: {datetime.now(UTC).isoformat()}")
        print("#"*60)

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())