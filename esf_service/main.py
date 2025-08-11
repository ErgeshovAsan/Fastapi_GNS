from fastapi import FastAPI, HTTPException
from tortoise.models import Model
from tortoise.contrib.fastapi import register_tortoise
from tortoise import fields
from pydantic import BaseModel
from typing import List, Optional
import httpx
from dotenv import load_dotenv
import os

app = FastAPI(title="ESF Service")

load_dotenv()

Delete_Document = os.getenv("Delete_Document")
Update_Document = os.getenv("Update_Document")
List_Document = os.getenv("List_Document")
Greate_Document = os.getenv("Greate_Document")

X_Road_Client = os.getenv("X_Road_Client")
ClientUUID = os.getenv("ClientUUID")
USER_TIN = os.getenv("USER_TIN")
Authorization = os.getenv("Authorization")

HEADERS = {
    "X-Road-Client": X_Road_Client,
    "ClientUUID": ClientUUID,
    "USER-TIN": USER_TIN,
    "Authorization": Authorization
}

class CatalogEntryIn(BaseModel):
    id: str
    catalogCode: str
    name: str
    unitCode: str
    unitClassificationCode: str
    quantity: int
    price: float
    taxRateVATCode: str
    salesTaxCode: str

    class Config:
        orm_mode = True

class InvoiceDeleteIn(BaseModel):
    documentUuid: str

class InvoiceIn(BaseModel):
    documentUuid: Optional[str] = None
    isBranchDataSent: bool
    ownedCrmReceiptCode: str
    contractorTin: str
    paymentCode: str
    taxRateVATCode: str
    isResident: bool
    deliveryDate: str
    currencyCode: str
    deliveryTypeCode: str
    deliveryCode: str
    operationTypeCode: str
    catalogEntries: List[CatalogEntryIn]

    class Config:
        orm_mode = True


class CatalogEntryOut(CatalogEntryIn):
    class Config:
        orm_mode = True


class InvoiceOut(BaseModel):
    id: int
    isBranchDataSent: bool
    ownedCrmReceiptCode: str
    contractorTin: str
    paymentCode: str
    taxRateVATCode: str
    isResident: bool
    deliveryDate: str
    currencyCode: str
    deliveryTypeCode: str
    deliveryCode: str
    operationTypeCode: str
    catalogEntries: List[CatalogEntryOut]

    class Config:
        orm_mode = True

class Invoice(Model):
    id = fields.IntField(pk=True)
    documentUuid = fields.CharField(max_length=100, unique=True, null=True)
    isBranchDataSent = fields.BooleanField()
    ownedCrmReceiptCode = fields.CharField(max_length=100)
    contractorTin = fields.CharField(max_length=14)
    paymentCode = fields.CharField(max_length=10)
    taxRateVATCode = fields.CharField(max_length=10)
    isResident = fields.BooleanField()
    deliveryDate = fields.CharField(max_length=20)
    currencyCode = fields.CharField(max_length=10)
    deliveryTypeCode = fields.CharField(max_length=10)
    deliveryCode = fields.CharField(max_length=10)
    operationTypeCode = fields.CharField(max_length=10)
    createdAt = fields.DatetimeField(auto_now_add=True)

    entries: fields.ReverseRelation["CatalogEntry"]

class CatalogEntry(Model):
    id = fields.IntField(pk=True)
    catalogCode = fields.CharField(max_length=100)
    name = fields.CharField(max_length=255)
    unitCode = fields.CharField(max_length=10)
    unitClassificationCode = fields.CharField(max_length=10)
    quantity = fields.IntField()
    price = fields.FloatField()
    taxRateVATCode = fields.CharField(max_length=10)
    salesTaxCode = fields.CharField(max_length=10)

    invoice = fields.ForeignKeyField("models.Invoice", related_name="entries")

@app.post("/invoice/send")
async def send_invoice(invoice: InvoiceIn):
    async with httpx.AsyncClient() as client:
        url = Greate_Document
        try:
            response = await client.post(
                url,
                headers=HEADERS,
                json=invoice.dict(),
                timeout=15.0
            )
            response.raise_for_status()
            gns_response = response.json()

            document_uuid = gns_response.get("documentUuid")
            if not document_uuid:
                raise HTTPException(status_code=500, detail="GNS did not return documentUuid")

            inv = await Invoice.create(
                documentUuid=document_uuid,
                isBranchDataSent=invoice.isBranchDataSent,
                ownedCrmReceiptCode=invoice.ownedCrmReceiptCode,
                contractorTin=invoice.contractorTin,
                paymentCode=invoice.paymentCode,
                taxRateVATCode=invoice.taxRateVATCode,
                isResident=invoice.isResident,
                deliveryDate=invoice.deliveryDate,
                currencyCode=invoice.currencyCode,
                deliveryTypeCode=invoice.deliveryTypeCode,
                deliveryCode=invoice.deliveryCode,
                operationTypeCode=invoice.operationTypeCode
            )

            for entry in invoice.catalogEntries:
                await CatalogEntry.create(
                    invoice=inv,
                    catalogCode=entry.catalogCode,
                    name=entry.name,
                    unitCode=entry.unitCode,
                    unitClassificationCode=entry.unitClassificationCode,
                    quantity=entry.quantity,
                    price=entry.price,
                    taxRateVATCode=entry.taxRateVATCode,
                    salesTaxCode=entry.salesTaxCode
                )

            return {
                "msg": "Invoice created in GNS and saved locally",
                "documentUuid": document_uuid,
                "gns_response": gns_response
            }

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=500,
                                detail=f"GNS responded with {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"GNS request failed: {str(e)}")

@app.get("/invoices/list")
async def get_all_invoices():
    async with httpx.AsyncClient() as client:
        url = List_Document
        try:
            response = await client.get(
                url,
                headers=HEADERS,
                timeout=15.0
            )
            response.raise_for_status()
            return {"gns_invoices": response.json()}
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=500,
                detail=f"GNS responded with {e.response.status_code}: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Request to GNS failed: {str(e)}"
            )


@app.put("/invoice/update/{documentUuid}")
async def update_invoice(documentUuid: str, updated_data: InvoiceIn):
    inv = await Invoice.get_or_none(documentUuid=documentUuid)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice_payload = updated_data.dict()
    invoice_payload["invoiceId"] = inv.documentUuid

    async with httpx.AsyncClient() as client:
        url = Update_Document.format(documentUuid=documentUuid)
        try:
            response = await client.put(
                url,
                headers=HEADERS,
                json=invoice_payload,
                timeout=15.0
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(500, f"GNS error: {e.response.status_code} — {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(500, f"Request error: {str(e)}")

    inv.isBranchDataSent = updated_data.isBranchDataSent
    inv.ownedCrmReceiptCode = updated_data.ownedCrmReceiptCode
    inv.contractorTin = updated_data.contractorTin
    inv.paymentCode = updated_data.paymentCode
    inv.taxRateVATCode = updated_data.taxRateVATCode
    inv.isResident = updated_data.isResident
    inv.deliveryDate = updated_data.deliveryDate
    inv.currencyCode = updated_data.currencyCode
    inv.deliveryTypeCode = updated_data.deliveryTypeCode
    inv.deliveryCode = updated_data.deliveryCode
    inv.operationTypeCode = updated_data.operationTypeCode
    await inv.save()

    await CatalogEntry.filter(invoice=inv).delete()

    for entry in updated_data.catalogEntries:
        await CatalogEntry.create(
            invoice=inv,
            catalogCode=entry.catalogCode,
            name=entry.name,
            unitCode=entry.unitCode,
            unitClassificationCode=entry.unitClassificationCode,
            quantity=entry.quantity,
            price=entry.price,
            taxRateVATCode=entry.taxRateVATCode,
            salesTaxCode=entry.salesTaxCode
        )

    return {"msg": "Invoice sent to GNS and updated in DB", "gns_response": response.json()}


@app.delete("/invoice/delete/{documentUuid}")
async def delete_invoice_by_uuid(documentUuid: str):
    inv = await Invoice.get_or_none(documentUuid=documentUuid).prefetch_related("entries")
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found in local DB")

    url = Delete_Document.format(documentUuid=documentUuid)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(url, headers=HEADERS, timeout=15.0)

            if response.status_code == 200:
                await CatalogEntry.filter(invoice=inv).delete()
                await inv.delete()
                return {"msg": f"Invoice with documentUuid={documentUuid} deleted locally and in GNS"}
            else:
                raise HTTPException(status_code=500, detail=f"GNS error: {response.status_code} — {response.text}")

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=500, detail=f"GNS error: {e.response.status_code} — {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")

    if inv:
        await CatalogEntry.filter(invoice=inv).delete()
        await inv.delete()
        return {
            "msg": f"Invoice with documentUuid={documentUuid} deleted from GNS and local DB"
        }
    else:
        return {
            "msg": f"Invoice deleted from GNS, but not found in local DB"
        }


register_tortoise(
    app,
    db_url="sqlite://esf_db.sqlite3",
    modules={"models": ["main"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

