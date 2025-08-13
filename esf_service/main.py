from fastapi import FastAPI, HTTPException
from tortoise.models import Model
from tortoise.contrib.fastapi import register_tortoise
from tortoise import fields
from pydantic import BaseModel
from typing import List, Optional
import httpx
from dotenv import load_dotenv
import os
import logging
import json
from tortoise.exceptions import IntegrityError

app = FastAPI(title="ESF Service")

load_dotenv()

Delete_Document = os.getenv("Delete_Document")
Update_Document = os.getenv("Update_Document")
List_Document = os.getenv("List_Document")
List_Document_UUid = os.getenv("List_Document_UUid")
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
    isBranchDataSent = fields.BooleanField(default=False)
    ownedCrmReceiptCode = fields.CharField(max_length=100, default="")
    contractorTin = fields.CharField(max_length=14, default="")
    paymentCode = fields.CharField(max_length=10, default="")
    taxRateVATCode = fields.CharField(max_length=10, default="")
    isResident = fields.BooleanField(default=False)
    deliveryDate = fields.CharField(max_length=20, default="")
    currencyCode = fields.CharField(max_length=10, default="")
    deliveryTypeCode = fields.CharField(max_length=10, default="")
    deliveryCode = fields.CharField(max_length=10, default="")
    operationTypeCode = fields.CharField(max_length=10, default="")
    createdDate = fields.CharField(max_length=30, default="")
    totalAmount = fields.FloatField(null=True)
    statusCode = fields.CharField(max_length=10, default="")


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

            return {
                "msg": "Invoice created in GNS",
                "documentUuid": document_uuid,
                "gns_response": gns_response
            }

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=500,
                                detail=f"GNS responded with {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"GNS request failed: {str(e)}")

async def save_invoice_with_entries(invoice_json: dict):
    isResident_str = invoice_json.get("isResident", "false")
    isResident = isResident_str.lower() == "true" if isinstance(isResident_str, str) else bool(isResident_str)

    documentUuid = invoice_json.get("documentUuid")
    deliveryCode = invoice_json.get("deliveryCode") or "UNKNOWN"

    try:
        inv = await Invoice.create(
            documentUuid=documentUuid,
            isBranchDataSent=invoice_json.get("isBranchDataSent", False),
            ownedCrmReceiptCode=invoice_json.get("ownedCrmReceiptCode", ""),
            contractorTin=invoice_json.get("contractor", {}).get("pin", ""),
            paymentCode=invoice_json.get("paymentType", {}).get("code", ""),
            taxRateVATCode=invoice_json.get("vatTaxType", {}).get("code", ""),
            isResident=isResident,
            deliveryDate=invoice_json.get("deliveryDate", ""),
            currencyCode=invoice_json.get("currency", {}).get("code", ""),
            deliveryTypeCode=invoice_json.get("deliveryType", {}).get("code", ""),
            deliveryCode=deliveryCode,
            operationTypeCode=invoice_json.get("receiptType", {}).get("code", ""),
            createdDate=invoice_json.get("createdDate", ""),
            totalAmount=invoice_json.get("totalAmount", 0.0),
            statusCode=invoice_json.get("statusCode", ""),
        )
    except IntegrityError:
        inv = await Invoice.get(documentUuid=documentUuid)
        inv.isBranchDataSent = invoice_json.get("isBranchDataSent", False)
        inv.ownedCrmReceiptCode = invoice_json.get("ownedCrmReceiptCode", "")
        inv.contractorTin = invoice_json.get("contractor", {}).get("pin", "")
        inv.paymentCode = invoice_json.get("paymentType", {}).get("code", "")
        inv.taxRateVATCode = invoice_json.get("vatTaxType", {}).get("code", "")
        inv.isResident = isResident
        inv.deliveryDate = invoice_json.get("deliveryDate", "")
        inv.currencyCode = invoice_json.get("currency", {}).get("code", "")
        inv.deliveryTypeCode = invoice_json.get("deliveryType", {}).get("code", "")
        inv.deliveryCode = deliveryCode
        inv.operationTypeCode = invoice_json.get("receiptType", {}).get("code", "")
        inv.createdDate = invoice_json.get("createdDate", "")
        inv.totalAmount = invoice_json.get("totalAmount", 0.0)
        inv.statusCode = invoice_json.get("statusCode", "")
        await inv.save()

    await CatalogEntry.filter(invoice=inv).delete()

    catalog_entries = invoice_json.get("catalogEntries", [])
    for entry in catalog_entries:
        await CatalogEntry.create(
            invoice=inv,
            catalogCode=entry.get("catalogCode", ""),
            name=entry.get("name", ""),
            unitCode=entry.get("unitCode", ""),
            unitClassificationCode=entry.get("unitClassificationCode", ""),
            quantity=entry.get("quantity", 0),
            price=entry.get("price", 0.0),
            taxRateVATCode=entry.get("taxRateVATCode", ""),
            salesTaxCode=entry.get("salesTaxCode", "")
        )

    return inv

async def save_all_invoices(data: dict):
    invoices = data.get("invoices", [])
    results = []
    for inv_json in invoices:
        inv = await save_invoice_with_entries(inv_json)
        results.append(inv)
    return results


@app.get("/invoice/realization/{exchange_code}")
async def fetch_invoice_from_gns(exchange_code: str):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                List_Document_UUid,
                params={"exchangeCode": exchange_code},
                headers=HEADERS,
                timeout=15.0
            )
            response.raise_for_status()
            data = response.json()
            logging.info("GNS raw response:\n" + json.dumps(data, indent=2, ensure_ascii=False))
            await save_all_invoices(data)
            return {"msg": "Invoice sent to GNS and updated in DB", "gns_response": response.json()}
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Ошибка сети при запросе к ГНС: {str(e)}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Ошибка ответа от ГНС: {e.response.text}")


@app.get("/invoices/list")
async def get_all_invoices():
    async with httpx.AsyncClient() as client:
        url = List_Document
        try:
            response = await client.get(url, headers=HEADERS, timeout=15.0)
            response.raise_for_status()

            data = response.json()

            invoices = data.get("invoices", [])

            for inv_json in invoices:
                doc_uuid = inv_json.get("documentUuid", "")
                if not doc_uuid:
                    print("Документ без UUID, пропускаем:", inv_json)
                    continue

                existing = await Invoice.filter(documentUuid=doc_uuid).first()
                if existing:
                    print(f"Обновляем счет с UUID: {doc_uuid}")
                    await existing.update_from_dict({
                        "isBranchDataSent": inv_json.get("isBranchDataSent", False),
                        "ownedCrmReceiptCode": inv_json.get("ownedCrmReceiptCode") or "",
                        "contractorTin": inv_json.get("contractorTin") or "",
                        "paymentCode": inv_json.get("paymentCode") or "",
                        "taxRateVATCode": inv_json.get("taxRateVATCode") or "",
                        "isResident": inv_json.get("isResident", False),
                        "deliveryDate": inv_json.get("deliveryDate") or "",
                        "currencyCode": inv_json.get("currencyCode") or "",
                        "deliveryTypeCode": inv_json.get("deliveryTypeCode") or "",
                        "deliveryCode": inv_json.get("deliveryCode") or "",
                        "operationTypeCode": inv_json.get("operationTypeCode") or "",
                        "createdDate": inv_json.get("createdDate") or "",
                        "totalAmount": inv_json.get("totalAmount"),
                        "statusCode": inv_json.get("statusCode") or "",
                    })
                    await existing.save()
                else:
                    print(f"Создаём новый счет с UUID: {doc_uuid}")
                    await Invoice.create(
                        documentUuid=inv_json.get("documentUuid") or "",
                        isBranchDataSent=inv_json.get("isBranchDataSent", False),
                        ownedCrmReceiptCode=inv_json.get("ownedCrmReceiptCode") or "",
                        contractorTin=inv_json.get("contractorTin") or "",
                        paymentCode=inv_json.get("paymentCode") or "",
                        taxRateVATCode=inv_json.get("taxRateVATCode") or "",
                        isResident=inv_json.get("isResident", False),
                        deliveryDate=inv_json.get("deliveryDate") or "",
                        currencyCode=inv_json.get("currencyCode") or "",
                        deliveryTypeCode=inv_json.get("deliveryTypeCode") or "",
                        deliveryCode=inv_json.get("deliveryCode") or "",
                        operationTypeCode=inv_json.get("operationTypeCode") or "",
                        createdDate=inv_json.get("createdDate") or "",
                        totalAmount=inv_json.get("totalAmount"),  # если nullable, можно так оставить
                        statusCode=inv_json.get("statusCode") or "",
                    )

            return {"gns_invoices": data}

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

