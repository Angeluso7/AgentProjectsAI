import requests
import io
import sys
from app.db.session import SessionLocal
from app.db.models.core import User, OrganizationMembership
from app.core.security import create_access_token

BASE_URL = "http://localhost:8000/api/v1"

# 1. Obtain admin token from DB
db = SessionLocal()
user = db.query(User).filter(User.is_active == True).first()
if not user:
    raise RuntimeError("No active user found in DB")
mem = db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id, OrganizationMembership.status == "active").first()
role = mem.role if mem else "admin"
token = create_access_token(user.id, email=user.email, extra_claims={"role": role})
db.close()

headers = {"Authorization": f"Bearer {token}"}
print(f"[AUTH] Created valid token for user {user.email} (role: {role}). Length: {len(token)}")

# 2. Create Project Alpha
res_a = requests.post(f"{BASE_URL}/projects/", json={
    "name": "Proyecto Alpha Visibility Test",
    "code": "PRJ-VIS-ALPHA",
    "description": "Testing project document visibility A",
    "stage": "Factibilidad"
}, headers=headers)
assert res_a.status_code == 201, f"Failed to create Alpha: {res_a.text}"
proj_a = res_a.json()
proj_a_id = proj_a["id"]
print(f"[PROJECT] Created Project Alpha: {proj_a_id} ({proj_a['code']})")

# 3. Create Project Beta
res_b = requests.post(f"{BASE_URL}/projects/", json={
    "name": "Proyecto Beta Visibility Test",
    "code": "PRJ-VIS-BETA",
    "description": "Testing project document visibility B",
    "stage": "Detalle"
}, headers=headers)
assert res_b.status_code == 201, f"Failed to create Beta: {res_b.text}"
proj_b = res_b.json()
proj_b_id = proj_b["id"]
print(f"[PROJECT] Created Project Beta: {proj_b_id} ({proj_b['code']})")

# Minimal PDF bytes
PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n00000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n200\n%%EOF"

# 4. Upload PDF to Project Alpha
files_a = {"file": ("plano_compartido.pdf", io.BytesIO(PDF_BYTES), "application/pdf")}
upload_a = requests.post(f"{BASE_URL}/projects/{proj_a_id}/documents", files=files_a, headers=headers)
assert upload_a.status_code == 201, f"Upload A failed: {upload_a.text}"
doc_a = upload_a.json()
print(f"[UPLOAD A] Uploaded to Alpha: doc_id={doc_a['id']}, project_id={doc_a['project_id']}, status={doc_a['processing_status']}")

# 5. List documents in Project Alpha
list_a = requests.get(f"{BASE_URL}/projects/{proj_a_id}/documents", headers=headers)
assert list_a.status_code == 200
docs_in_a = list_a.json()
assert len(docs_in_a) == 1, f"Expected 1 document in Alpha, got {len(docs_in_a)}"
assert docs_in_a[0]["id"] == doc_a["id"]
print(f"[VERIFY A] Project Alpha has 1 document: {docs_in_a[0]['filename']} (immediate visibility OK)")

# 6. Upload EXACT SAME PDF to Project Beta
files_b = {"file": ("plano_compartido.pdf", io.BytesIO(PDF_BYTES), "application/pdf")}
upload_b = requests.post(f"{BASE_URL}/projects/{proj_b_id}/documents", files=files_b, headers=headers)
assert upload_b.status_code == 201, f"Upload B failed: {upload_b.text}"
doc_b = upload_b.json()
print(f"[UPLOAD B] Uploaded to Beta: doc_id={doc_b['id']}, project_id={doc_b['project_id']}, status={doc_b['processing_status']}")

assert doc_b["id"] != doc_a["id"], f"CRITICAL BUG: doc_b has same ID as doc_a ({doc_b['id']})"
assert doc_b["project_id"] == proj_b_id, f"doc_b project_id ({doc_b['project_id']}) != proj_b_id ({proj_b_id})"

# 7. List documents in Project Beta
list_b = requests.get(f"{BASE_URL}/projects/{proj_b_id}/documents", headers=headers)
assert list_b.status_code == 200
docs_in_b = list_b.json()
assert len(docs_in_b) == 1, f"Expected 1 document in Beta, got {len(docs_in_b)}"
assert docs_in_b[0]["id"] == doc_b["id"]
print(f"[VERIFY B] Project Beta has 1 document: {docs_in_b[0]['filename']} (isolation OK)")

# 8. Re-check Project Alpha documents (cross-isolation)
list_a_again = requests.get(f"{BASE_URL}/projects/{proj_a_id}/documents", headers=headers)
docs_in_a_again = list_a_again.json()
assert len(docs_in_a_again) == 1, f"Expected 1 document in Alpha, got {len(docs_in_a_again)}"
assert docs_in_a_again[0]["id"] == doc_a["id"]
print("[VERIFY CROSS] Cross-isolation verified: Alpha documents untouched by Beta upload")

# 9. Test same project uploading same file again (Idempotency)
files_a2 = {"file": ("plano_compartido.pdf", io.BytesIO(PDF_BYTES), "application/pdf")}
upload_a2 = requests.post(f"{BASE_URL}/projects/{proj_a_id}/documents", files=files_a2, headers=headers)
assert upload_a2.status_code == 201
doc_a2 = upload_a2.json()
assert doc_a2["id"] == doc_a["id"], "Idempotency policy should return existing document"
list_a3 = requests.get(f"{BASE_URL}/projects/{proj_a_id}/documents", headers=headers).json()
assert len(list_a3) == 1, f"Duplicate was created! Total docs in Alpha: {len(list_a3)}"
print(f"[IDEMPOTENCY] Uploading duplicate file to same project returned existing document {doc_a2['id']} without duplicate")

# 10. Download test
dl_a = requests.get(f"{BASE_URL}/projects/{proj_a_id}/documents/{doc_a['id']}/download", headers=headers)
assert dl_a.status_code == 200, f"Download A failed: {dl_a.status_code}"
assert dl_a.content == PDF_BYTES, "Downloaded content does not match original bytes"
print(f"[DOWNLOAD] Successfully downloaded {len(dl_a.content)} bytes from Alpha document")

# 11. Process and Retry test
proc_res = requests.post(f"{BASE_URL}/projects/{proj_a_id}/documents/{doc_a['id']}/process", headers=headers)
assert proc_res.status_code == 200, f"Process failed: {proc_res.text}"
print(f"[PROCESS] Process endpoint succeeded. Status: {proc_res.json()['processing_status']}")

retry_res = requests.post(f"{BASE_URL}/projects/{proj_a_id}/documents/{doc_a['id']}/retry", headers=headers)
assert retry_res.status_code == 200, f"Retry failed: {retry_res.text}"
assert retry_res.json()["id"] == doc_a["id"], "Retry must preserve document_id"
print(f"[RETRY] Retry endpoint succeeded. Status: {retry_res.json()['processing_status']}")

# 12. Delete document from Alpha
del_a = requests.delete(f"{BASE_URL}/projects/{proj_a_id}/documents/{doc_a['id']}", headers=headers)
assert del_a.status_code == 200, f"Delete A failed: {del_a.text}"

list_a_after = requests.get(f"{BASE_URL}/projects/{proj_a_id}/documents", headers=headers).json()
assert len(list_a_after) == 0, f"Alpha should have 0 docs, got {len(list_a_after)}"

list_b_after = requests.get(f"{BASE_URL}/projects/{proj_b_id}/documents", headers=headers).json()
assert len(list_b_after) == 1, f"Beta doc should NOT be deleted! Got {len(list_b_after)}"
assert list_b_after[0]["id"] == doc_b["id"]
print("[DELETE ISOLATION] Deleting Alpha doc did NOT affect Beta doc with same hash!")

# 13. Cleanup test projects
requests.post(f"{BASE_URL}/projects/{proj_a_id}/delete-confirmed", json={"confirmation_code": "PRJ-VIS-ALPHA", "mode": "hard_delete"}, headers=headers)
requests.post(f"{BASE_URL}/projects/{proj_b_id}/delete-confirmed", json={"confirmation_code": "PRJ-VIS-BETA", "mode": "hard_delete"}, headers=headers)
print("[CLEANUP] Test projects cleaned up successfully.")

print("\nALL HTTP AND DB VALIDATION CHECKS PASSED 100%!")
