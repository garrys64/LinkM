# =========================================================
#
# PROCESSOR XmlConverterProcessor
# 
# =========================================================

#!/usr/bin/env python3
"""
Convert UN/CEFACT CrossIndustryInvoice (CII) XML to UBL 2.1 Invoice/CreditNote.

The converter is intentionally structured around EN 16931 business terms (BTs):
values are read from the CII syntax binding and emitted to the corresponding
UBL 2.1 syntax binding. It covers the common core invoice/credit-note fields
used by EN 16931 and is designed to be extended with more BT mappings.
"""

from __future__ import annotations


import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable
import streamlit as st
import os
import io
from pathlib import Path
import subprocess
#from lxml import etree


CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}

UBL_INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
UBL_CREDIT_NOTE_NS = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"

ET.register_namespace("", UBL_INVOICE_NS)
ET.register_namespace("cbc", CBC_NS)
ET.register_namespace("cac", CAC_NS)


CUSTOMIZATION_ID_1 = "urn:cen.eu:en16931:2017"
CUSTOMIZATION_ID_3 = "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
PEPPOL_BILLING_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

#
BUSINESS_PROCESS_TYPE_ID = "BGT-010"
#

INVOICE_TYPE_TO_CREDIT_NOTE = {"381", "396", "532"}
PEPPOL3 = "Peppol BIS/POACC 3.0"
SCRIPT_DIR = Path(__file__).parent

PAYMENT_MEANS_CODE_MAP = {
    # CII and UBL both use UNCL 4461 for EN 16931, so most values pass through.
    "10": "10",  # In cash
    "20": "20",  # Cheque
    "30": "30",  # Credit transfer
    "31": "31",  # Debit transfer
    "42": "42",  # Payment to bank account
    "48": "48",  # Bank card
    "49": "49",  # Direct debit
    "58": "58",  # SEPA credit transfer
    "59": "59",  # SEPA direct debit
}


@dataclass(frozen=True)
class MappingRow:
    bt: str
    name: str
    cii: str
    ubl_invoice: str
    status: str = "implemented"


MAPPING_ROWS = [
    MappingRow("BT-1", "Invoice number", "rsm:ExchangedDocument/ram:ID", "cbc:ID"),
    MappingRow("BT-2", "Invoice issue date", "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString", "cbc:IssueDate"),
    MappingRow("BT-3", "Invoice type code", "rsm:ExchangedDocument/ram:TypeCode", "cbc:InvoiceTypeCode|cbc:CreditNoteTypeCode"),
    MappingRow("BT-5", "Invoice currency code", "ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode", "cbc:DocumentCurrencyCode"),
    MappingRow("BT-6", "VAT accounting currency code", "ram:ApplicableHeaderTradeSettlement/ram:TaxCurrencyCode", "cbc:TaxCurrencyCode"),
    MappingRow("BT-10", "Buyer reference", "ram:ApplicableHeaderTradeAgreement/ram:BuyerReference", "cbc:BuyerReference"),
    MappingRow("BT-13", "Purchase order reference", "ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID", "cac:OrderReference/cbc:ID"),
    MappingRow("BT-20", "Payment terms", "ram:SpecifiedTradePaymentTerms/ram:Description", "cac:PaymentTerms/cbc:Note"),
    MappingRow("BT-23", "Business process type", "constant/default", "cbc:ProfileID"),
    MappingRow("BT-24", "Specification identifier", "constant/default", "cbc:CustomizationID"),
    MappingRow("BT-27", "Seller name", "ram:SellerTradeParty/ram:Name", "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName"),
    MappingRow("BT-31", "Seller VAT identifier", "ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']", "cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID"),
    MappingRow("BT-44", "Buyer name", "ram:BuyerTradeParty/ram:Name", "cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName"),
    MappingRow("BT-48", "Buyer VAT identifier", "ram:BuyerTradeParty/ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']", "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID"),
    MappingRow("BT-72", "Actual delivery date", "ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString", "cac:Delivery/cbc:ActualDeliveryDate"),
    MappingRow("BT-81", "Payment means type code", "ram:SpecifiedTradeSettlementPaymentMeans/ram:TypeCode", "cac:PaymentMeans/cbc:PaymentMeansCode"),
    MappingRow("BT-83", "Remittance information", "ram:ApplicableHeaderTradeSettlement/ram:PaymentReference", "cac:PaymentMeans/cbc:PaymentID"),
    MappingRow("BT-84", "Payment account identifier", "ram:PayeePartyCreditorFinancialAccount/ram:IBANID|ram:ProprietaryID", "cac:PayeeFinancialAccount/cbc:ID"),
    MappingRow("BT-106", "Sum of invoice line net amount", "ram:LineTotalAmount", "cac:LegalMonetaryTotal/cbc:LineExtensionAmount"),
    MappingRow("BT-107", "Sum of allowances", "ram:AllowanceTotalAmount", "cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount"),
    MappingRow("BT-108", "Sum of charges", "ram:ChargeTotalAmount", "cac:LegalMonetaryTotal/cbc:ChargeTotalAmount"),
    MappingRow("BT-109", "Invoice total amount without VAT", "ram:TaxBasisTotalAmount", "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount"),
    MappingRow("BT-110", "Invoice total VAT amount", "ram:TaxTotalAmount", "cac:TaxTotal/cbc:TaxAmount"),
    MappingRow("BT-112", "Invoice total amount with VAT", "ram:GrandTotalAmount", "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount"),
    MappingRow("BT-113", "Paid amount", "ram:TotalPrepaidAmount", "cac:LegalMonetaryTotal/cbc:PrepaidAmount"),
    MappingRow("BT-115", "Amount due for payment", "ram:DuePayableAmount", "cac:LegalMonetaryTotal/cbc:PayableAmount"),
    MappingRow("BT-116", "VAT category taxable amount", "ram:ApplicableTradeTax/ram:BasisAmount", "cac:TaxSubtotal/cbc:TaxableAmount"),
    MappingRow("BT-117", "VAT category tax amount", "ram:ApplicableTradeTax/ram:CalculatedAmount", "cac:TaxSubtotal/cbc:TaxAmount"),
    MappingRow("BT-118", "VAT category code", "ram:ApplicableTradeTax/ram:CategoryCode", "cac:TaxSubtotal/cac:TaxCategory/cbc:ID"),
    MappingRow("BT-119", "VAT category rate", "ram:ApplicableTradeTax/ram:RateApplicablePercent", "cac:TaxSubtotal/cac:TaxCategory/cbc:Percent"),
    MappingRow("BT-126", "Invoice line identifier", "ram:AssociatedDocumentLineDocument/ram:LineID", "cac:InvoiceLine/cbc:ID"),
    MappingRow("BT-129", "Invoiced quantity", "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", "cac:InvoiceLine/cbc:InvoicedQuantity|cbc:CreditedQuantity"),
    MappingRow("BT-130", "Invoiced quantity unit", "ram:BilledQuantity/@unitCode", "cbc:InvoicedQuantity/@unitCode|cbc:CreditedQuantity/@unitCode"),
    MappingRow("BT-131", "Invoice line net amount", "ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount", "cac:InvoiceLine/cbc:LineExtensionAmount"),
    MappingRow("BT-146", "Item net price", "ram:NetPriceProductTradePrice/ram:ChargeAmount", "cac:Price/cbc:PriceAmount"),
    MappingRow("BT-148", "Item gross price", "ram:GrossPriceProductTradePrice/ram:ChargeAmount", "cac:Price/cac:AllowanceCharge/cbc:BaseAmount"),
    MappingRow("BT-151", "Line VAT category code", "ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:CategoryCode", "cac:ClassifiedTaxCategory/cbc:ID"),
    MappingRow("BT-152", "Line VAT rate", "ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:RateApplicablePercent", "cac:ClassifiedTaxCategory/cbc:Percent"),
    MappingRow("BT-153", "Item name", "ram:SpecifiedTradeProduct/ram:Name", "cac:Item/cbc:Name"),
    MappingRow("BT-154", "Item description", "ram:SpecifiedTradeProduct/ram:Description", "cac:Item/cbc:Description"),
    MappingRow("BT-155", "Seller item identifier", "ram:SpecifiedTradeProduct/ram:SellerAssignedID", "cac:SellersItemIdentification/cbc:ID"),
    MappingRow("BT-156", "Buyer item identifier", "ram:SpecifiedTradeProduct/ram:BuyerAssignedID", "cac:BuyersItemIdentification/cbc:ID"),
    MappingRow("BT-157", "Standard item identifier", "ram:SpecifiedTradeProduct/ram:GlobalID", "cac:StandardItemIdentification/cbc:ID"),
]



# Das ist Beispiel! Mann muss wechseln zu real CUSTOMERs
#-------------------------------------------------------------
CUSTOMER_CONFIG = {
    "CUSTOMER A": {"schemeID": "0088", "GLN": "4012345678901"},
    "CUSTOMER B": {"schemeID": "0085", "GLN": "5012345678901"},
    "CUSTOMER C": {"schemeID": "0086", "GLN": "6012345678901"}
}
my_schemeID = "0088"
my_GLN = "4012345678901"
#---------------------------------------------------------------

from processors.BaseProcessor import BaseProcessor

class XmlConverter_CIItoUBL(BaseProcessor):

    name = "XmlConverter_CIItoUBL"

    def render_ui(self):     
            
        Datendatei = st.file_uploader("XML Datei in Format CrossIndustryInvoice", type=["xml"])
        profile_xml = st.selectbox("PROFILE",["STANDARD EN 16931/Peppol 1.0", PEPPOL3])
        
        CUSTOMIZATION_ID = CUSTOMIZATION_ID_1
        schemeID = ""
        GLN = ""
        if profile_xml == PEPPOL3:

            CUSTOMIZATION_ID = CUSTOMIZATION_ID_3
            #PEPPOL_BILLING_PROFILE_ID = ""

            profile_Customer = st.selectbox(
                "CUSTOMER:",
                list(CUSTOMER_CONFIG.keys()),  # Показываем только названия
                key="profile_Customer_select"
            )
            
            params = CUSTOMER_CONFIG[profile_Customer]
            schemeID = params["schemeID"]
            GLN = params["GLN"]
        
        
        return {
            "Datendatei": Datendatei,
            "profile_xml": profile_xml,
            "CUSTOMIZATION_ID": CUSTOMIZATION_ID,
            "schemeID": schemeID,
            "GLN": GLN       
        }

    def process(self, data):

        Datendatei = data["Datendatei"]
        profile_xml = data["profile_xml"]
        CUSTOMIZATION_ID = data["CUSTOMIZATION_ID"]
        schemeID = data["schemeID"]
        GLN = data["GLN"]
        
        output_files = []


        
            
            


        try:  
                    
            def q(ns: str, tag: str) -> str:
                return f"{{{ns}}}{tag}"


            def cbc(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
                child = ET.SubElement(parent, q(CBC_NS, tag), {k: v for k, v in attrs.items() if v is not None})
                if text is not None:
                    child.text = str(text)
                return child


            def cac(parent: ET.Element, tag: str) -> ET.Element:
                return ET.SubElement(parent, q(CAC_NS, tag))


            def first(context: ET.Element | None, paths: Iterable[str]) -> ET.Element | None:
                if context is None:
                    return None
                for path in paths:
                    found = context.find(path, CII_NS)
                    if found is not None and (found.text or found.attrib or len(found)):
                        return found
                return None


            def text(context: ET.Element | None, *paths: str) -> str | None:
                node = first(context, paths)
                if node is None or node.text is None:
                    return None
                value = node.text.strip()
                return value or None


            def money_attrs(node: ET.Element | None, default_currency: str | None) -> dict[str, str]:
                currency = node.attrib.get("currencyID") if node is not None else None
                return {"currencyID": currency or default_currency} if currency or default_currency else {}


            def date_text(context: ET.Element | None, *paths: str) -> str | None:
                node = first(context, paths)
                if node is None or node.text is None:
                    return None
                raw = node.text.strip()
                if not raw:
                    return None
                fmt = node.attrib.get("format")
                if fmt == "102" and len(raw) == 8:
                    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
                if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
                    return raw[0:10]
                return raw


            def decimal_difference(left: str | None, right: str | None) -> str | None:
                if left is None or right is None:
                    return None
                try:
                    value = Decimal(left) - Decimal(right)
                except InvalidOperation:
                    return None
                return format(value, "f")


            def add_if_text(parent: ET.Element, namespace_func, tag: str, value: str | None, **attrs: str) -> ET.Element | None:
                if value is None:
                    return None
                return namespace_func(parent, tag, value, **attrs)


            def find_trade_transaction(root: ET.Element) -> ET.Element:
                trx = root.find("rsm:SupplyChainTradeTransaction", CII_NS)
                if trx is None:
                    raise ValueError("CII document does not contain rsm:SupplyChainTradeTransaction")
                return trx


            def find_header_agreement(trx: ET.Element) -> ET.Element | None:
                return trx.find("ram:ApplicableHeaderTradeAgreement", CII_NS)


            def find_header_delivery(trx: ET.Element) -> ET.Element | None:
                return trx.find("ram:ApplicableHeaderTradeDelivery", CII_NS)


            def find_header_settlement(trx: ET.Element) -> ET.Element | None:
                return trx.find("ram:ApplicableHeaderTradeSettlement", CII_NS)


            def tax_scheme_id(category: str | None = None) -> str:
                return "VAT"


            def add_party(parent: ET.Element, role_tag: str, party: ET.Element | None) -> None:
                if party is None:
                    return

                wrapper = cac(parent, role_tag)
                ubl_party = cac(wrapper, "Party")

                endpoint = first(party, ["ram:URIUniversalCommunication/ram:URIID"])
    ##                  
                if profile_xml ==  PEPPOL3: 
                    if role_tag ==  'AccountingCustomerParty':                     
                        cbc(ubl_party, "EndpointID", text=GLN,schemeID=schemeID)
                    else:
                        cbc(ubl_party, "EndpointID", text=my_GLN,schemeID=my_schemeID)
                else:
                    if endpoint is not None and endpoint.text:
                        attrs = {}
                        if endpoint.attrib.get("schemeID"):
                            attrs["schemeID"] = endpoint.attrib["schemeID"]
                        cbc(ubl_party, "EndpointID", endpoint.text.strip(), **attrs)
    ##

                party_id = first(party, ["ram:ID", "ram:GlobalID"])
                if party_id is not None and party_id.text:
                    party_ident = cac(ubl_party, "PartyIdentification")
                    attrs = {}
                    if party_id.attrib.get("schemeID"):
                        attrs["schemeID"] = party_id.attrib["schemeID"]
                    cbc(party_ident, "ID", party_id.text.strip(), **attrs)

                name_value = text(party, "ram:Name")
                if name_value:
                    party_name = cac(ubl_party, "PartyName")
                    cbc(party_name, "Name", name_value)

                address = party.find("ram:PostalTradeAddress", CII_NS)
                if address is not None:
                    postal = cac(ubl_party, "PostalAddress")
                    add_if_text(postal, cbc, "StreetName", text(address, "ram:LineOne"))
                    add_if_text(postal, cbc, "AdditionalStreetName", text(address, "ram:LineTwo"))
                    add_if_text(postal, cbc, "CityName", text(address, "ram:CityName"))
                    add_if_text(postal, cbc, "PostalZone", text(address, "ram:PostcodeCode"))
                    add_if_text(postal, cbc, "CountrySubentity", text(address, "ram:CountrySubDivisionName"))
                    country_code = text(address, "ram:CountryID")
                    if country_code:
                        country = cac(postal, "Country")
                        cbc(country, "IdentificationCode", country_code)

                vat_id = tax_registration_id(party, "VA")
                if vat_id:
                    tax_scheme = cac(ubl_party, "PartyTaxScheme")
                    cbc(tax_scheme, "CompanyID", vat_id)
                    scheme = cac(tax_scheme, "TaxScheme")
                    cbc(scheme, "ID", "VAT")

                legal = cac(ubl_party, "PartyLegalEntity")
                cbc(legal, "RegistrationName", name_value or "")
                legal_reg = tax_registration_id(party, "FC") or text(party, "ram:ID")
                if legal_reg:
                    cbc(legal, "CompanyID", legal_reg)

                contact_name = text(party, "ram:DefinedTradeContact/ram:PersonName")
                phone = text(party, "ram:DefinedTradeContact/ram:TelephoneUniversalCommunication/ram:CompleteNumber")
                email = text(party, "ram:DefinedTradeContact/ram:EmailURIUniversalCommunication/ram:URIID")
                if contact_name or phone or email:
                    contact = cac(ubl_party, "Contact")
                    add_if_text(contact, cbc, "Name", contact_name)
                    add_if_text(contact, cbc, "Telephone", phone)
                    add_if_text(contact, cbc, "ElectronicMail", email)


            def tax_registration_id(party: ET.Element, scheme_id: str) -> str | None:
                for registration in party.findall("ram:SpecifiedTaxRegistration", CII_NS):
                    node = registration.find("ram:ID", CII_NS)
                    if node is not None and node.text and node.attrib.get("schemeID") == scheme_id:
                        return node.text.strip()
                return None


            def add_document_references(parent: ET.Element, agreement: ET.Element | None) -> None:
                if agreement is None:
                    return
                order_id = text(agreement, "ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID")
                if order_id:
                    order = cac(parent, "OrderReference")
                    cbc(order, "ID", order_id)

                contract_id = text(agreement, "ram:ContractReferencedDocument/ram:IssuerAssignedID")
                if contract_id:
                    contract = cac(parent, "ContractDocumentReference")
                    cbc(contract, "ID", contract_id)

                for doc in agreement.findall("ram:AdditionalReferencedDocument", CII_NS):
                    doc_id = text(doc, "ram:IssuerAssignedID")
                    if doc_id:
                        ref = cac(parent, "AdditionalDocumentReference")
                        cbc(ref, "ID", doc_id)
                        add_if_text(ref, cbc, "DocumentTypeCode", text(doc, "ram:TypeCode"))
                        add_if_text(ref, cbc, "DocumentDescription", text(doc, "ram:Name"))


            def add_delivery(parent: ET.Element, delivery: ET.Element | None) -> None:
                if delivery is None:
                    return
                actual_date = date_text(
                    delivery,
                    "ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString",
                )
                if actual_date:
                    delivery_out = cac(parent, "Delivery")
                    cbc(delivery_out, "ActualDeliveryDate", actual_date)


            def add_payment(parent: ET.Element, settlement: ET.Element | None) -> None:
                if settlement is None:
                    return
                for means in settlement.findall("ram:SpecifiedTradeSettlementPaymentMeans", CII_NS):
                    means_code = text(means, "ram:TypeCode")
                    payment_id = text(settlement, "ram:PaymentReference")
                    account_id = text(
                        means,
                        "ram:PayeePartyCreditorFinancialAccount/ram:IBANID",
                        "ram:PayeePartyCreditorFinancialAccount/ram:ProprietaryID",
                    )
                    account_name = text(means, "ram:PayeePartyCreditorFinancialAccount/ram:AccountName")
                    bic = text(means, "ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID")
                    mandate = text(means, "ram:ApplicableTradeSettlementFinancialCard/ram:ID")

                    if not any([means_code, payment_id, account_id, account_name, bic, mandate]):
                        continue

                    out = cac(parent, "PaymentMeans")
                    if means_code:
                        cbc(out, "PaymentMeansCode", PAYMENT_MEANS_CODE_MAP.get(means_code, means_code))
                    add_if_text(out, cbc, "PaymentID", payment_id)
                    if mandate:
                        mandate_out = cac(out, "PaymentMandate")
                        cbc(mandate_out, "ID", mandate)
                    if account_id or account_name or bic:
                        account = cac(out, "PayeeFinancialAccount")
                        add_if_text(account, cbc, "ID", account_id)
                        add_if_text(account, cbc, "Name", account_name)
                        if bic:
                            branch = cac(account, "FinancialInstitutionBranch")
                            cbc(branch, "ID", bic)

                for terms in settlement.findall("ram:SpecifiedTradePaymentTerms", CII_NS):
                    note = text(terms, "ram:Description")
                    due_date = date_text(terms, "ram:DueDateDateTime/udt:DateTimeString")
                    if note or due_date:
                        out = cac(parent, "PaymentTerms")
                        add_if_text(out, cbc, "Note", note)
    #                            add_if_text(out, cbc, "PaymentDueDate", due_date)


            def add_tax_total(parent: ET.Element, settlement: ET.Element | None, currency: str | None) -> None:
                if settlement is None:
                    return

                tax_total_amount_node = first(settlement, ["ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxTotalAmount"])
                taxes = settlement.findall("ram:ApplicableTradeTax", CII_NS)
                if tax_total_amount_node is None and not taxes:
                    return

                tax_total = cac(parent, "TaxTotal")
                if tax_total_amount_node is not None and tax_total_amount_node.text:
                    cbc(tax_total, "TaxAmount", tax_total_amount_node.text.strip(), **money_attrs(tax_total_amount_node, currency))
                else:
                    cbc(tax_total, "TaxAmount", "0", **({"currencyID": currency} if currency else {}))

                for tax in taxes:
                    subtotal = cac(tax_total, "TaxSubtotal")
                    basis = first(tax, ["ram:BasisAmount"])
                    calculated = first(tax, ["ram:CalculatedAmount"])
                    add_if_text(subtotal, cbc, "TaxableAmount", basis.text.strip() if basis is not None and basis.text else None, **money_attrs(basis, currency))
                    add_if_text(subtotal, cbc, "TaxAmount", calculated.text.strip() if calculated is not None and calculated.text else None, **money_attrs(calculated, currency))

                    category = cac(subtotal, "TaxCategory")
                    category_code = text(tax, "ram:CategoryCode")
                    percent = text(tax, "ram:RateApplicablePercent")
                    add_if_text(category, cbc, "ID", category_code)
                    add_if_text(category, cbc, "Percent", percent)
                    scheme = cac(category, "TaxScheme")
                    cbc(scheme, "ID", tax_scheme_id(category_code))


            def add_legal_monetary_total(parent: ET.Element, settlement: ET.Element | None, currency: str | None, is_credit_note: bool) -> None:
                if settlement is None:
                    return
                summation = settlement.find("ram:SpecifiedTradeSettlementHeaderMonetarySummation", CII_NS)
                if summation is None:
                    return

                total = cac(parent, "LegalMonetaryTotal" if not is_credit_note else "LegalMonetaryTotal")
                monetary_fields = [
                    ("LineExtensionAmount", "ram:LineTotalAmount"),
                    ("TaxExclusiveAmount", "ram:TaxBasisTotalAmount"),
                    ("TaxInclusiveAmount", "ram:GrandTotalAmount"),
                    ("AllowanceTotalAmount", "ram:AllowanceTotalAmount"),
                    ("ChargeTotalAmount", "ram:ChargeTotalAmount"),
                    ("PrepaidAmount", "ram:TotalPrepaidAmount"),
                    ("PayableRoundingAmount", "ram:RoundingAmount"),
                    ("PayableAmount", "ram:DuePayableAmount"),
                ]
                for ubl_tag, cii_path in monetary_fields:
                    node = first(summation, [cii_path])
                    if node is not None and node.text:
                        cbc(total, ubl_tag, node.text.strip(), **money_attrs(node, currency))


            def add_allowance_charges(parent: ET.Element, settlement: ET.Element | None, currency: str | None) -> None:
                if settlement is None:
                    return
                for ac in settlement.findall("ram:SpecifiedTradeAllowanceCharge", CII_NS):
                    actual = text(ac, "ram:ActualAmount")
                    if not actual:
                        continue
                    indicator = text(ac, "ram:ChargeIndicator/udt:Indicator")
                    out = cac(parent, "AllowanceCharge")
                    cbc(out, "ChargeIndicator", "true" if indicator and indicator.lower() == "true" else "false")
                    add_if_text(out, cbc, "AllowanceChargeReason", text(ac, "ram:Reason"))
                    amount_node = first(ac, ["ram:ActualAmount"])
                    cbc(out, "Amount", actual, **money_attrs(amount_node, currency))
                    tax = ac.find("ram:CategoryTradeTax", CII_NS)
                    if tax is not None:
                        category = cac(out, "TaxCategory")
                        add_if_text(category, cbc, "ID", text(tax, "ram:CategoryCode"))
                        add_if_text(category, cbc, "Percent", text(tax, "ram:RateApplicablePercent"))
                        scheme = cac(category, "TaxScheme")
                        cbc(scheme, "ID", "VAT")


            def add_lines(parent: ET.Element, trx: ET.Element, currency: str | None, is_credit_note: bool) -> None:
                line_tag = "CreditNoteLine" if is_credit_note else "InvoiceLine"
                quantity_tag = "CreditedQuantity" if is_credit_note else "InvoicedQuantity"

                for index, line in enumerate(trx.findall("ram:IncludedSupplyChainTradeLineItem", CII_NS), start=1):
                    out = cac(parent, line_tag)
                    cbc(out, "ID", text(line, "ram:AssociatedDocumentLineDocument/ram:LineID") or str(index))

                    quantity_node = first(line, ["ram:SpecifiedLineTradeDelivery/ram:BilledQuantity"])
                    if quantity_node is not None and quantity_node.text:
                        attrs = {}
                        if quantity_node.attrib.get("unitCode"):
                            attrs["unitCode"] = quantity_node.attrib["unitCode"]
                        cbc(out, quantity_tag, quantity_node.text.strip(), **attrs)

                    line_total = first(line, ["ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount"])
                    if line_total is not None and line_total.text:
                        cbc(out, "LineExtensionAmount", line_total.text.strip(), **money_attrs(line_total, currency))

                    line_settlement = line.find("ram:SpecifiedLineTradeSettlement", CII_NS)
                    if line_settlement is not None:
                        for ac in line_settlement.findall("ram:SpecifiedTradeAllowanceCharge", CII_NS):
                            actual = text(ac, "ram:ActualAmount")
                            if actual:
                                ac_out = cac(out, "AllowanceCharge")
                                indicator = text(ac, "ram:ChargeIndicator/udt:Indicator")
                                cbc(ac_out, "ChargeIndicator", "true" if indicator and indicator.lower() == "true" else "false")
                                add_if_text(ac_out, cbc, "AllowanceChargeReason", text(ac, "ram:Reason"))
                                amount_node = first(ac, ["ram:ActualAmount"])
                                cbc(ac_out, "Amount", actual, **money_attrs(amount_node, currency))

                    product = line.find("ram:SpecifiedTradeProduct", CII_NS)
                    item = cac(out, "Item")
                    add_if_text(item, cbc, "Description", text(product, "ram:Description") if product is not None else None)
                    cbc(item, "Name", text(product, "ram:Name") if product is not None else "")

                    if product is not None:
                        seller_id = text(product, "ram:SellerAssignedID")
                        if seller_id:
                            ident = cac(item, "SellersItemIdentification")
                            cbc(ident, "ID", seller_id)
                        buyer_id = text(product, "ram:BuyerAssignedID")
                        if buyer_id:
                            ident = cac(item, "BuyersItemIdentification")
                            cbc(ident, "ID", buyer_id)
                        global_id = first(product, ["ram:GlobalID"])
                        if global_id is not None and global_id.text:
                            ident = cac(item, "StandardItemIdentification")
                            attrs = {}
                            if global_id.attrib.get("schemeID"):
                                attrs["schemeID"] = global_id.attrib["schemeID"]
                            cbc(ident, "ID", global_id.text.strip(), **attrs)

                    tax = first(line, ["ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax"])
                    if tax is not None:
                        classified = cac(item, "ClassifiedTaxCategory")
                        category = text(tax, "ram:CategoryCode")
                        percent = text(tax, "ram:RateApplicablePercent")
                        add_if_text(classified, cbc, "ID", category)
                        add_if_text(classified, cbc, "Percent", percent)
                        scheme = cac(classified, "TaxScheme")
                        cbc(scheme, "ID", "VAT")

                    price = cac(out, "Price")
                    net_price = first(line, ["ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount"])
                    gross_price = first(line, ["ram:SpecifiedLineTradeAgreement/ram:GrossPriceProductTradePrice/ram:ChargeAmount"])
                    price_basis = first(line, ["ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:BasisQuantity"])
                    if net_price is not None and net_price.text:
                        cbc(price, "PriceAmount", net_price.text.strip(), **money_attrs(net_price, currency))
                    elif gross_price is not None and gross_price.text:
                        cbc(price, "PriceAmount", gross_price.text.strip(), **money_attrs(gross_price, currency))
                    if price_basis is not None and price_basis.text:
                        attrs = {}
                        if price_basis.attrib.get("unitCode"):
                            attrs["unitCode"] = price_basis.attrib["unitCode"]
                        cbc(price, "BaseQuantity", price_basis.text.strip(), **attrs)
                    if gross_price is not None and gross_price.text and net_price is not None and net_price.text:
                        gross_value = gross_price.text.strip()
                        net_value = net_price.text.strip()
                        allowance_amount = text(
                            line,
                            "ram:SpecifiedLineTradeAgreement/ram:GrossPriceProductTradePrice/ram:AppliedTradeAllowanceCharge/ram:ActualAmount",
                        )
                        allowance_amount = allowance_amount or decimal_difference(gross_value, net_value)
                        if allowance_amount:
                            ac = cac(price, "AllowanceCharge")
                            cbc(ac, "ChargeIndicator", "false")
                            cbc(ac, "Amount", allowance_amount, **money_attrs(gross_price, currency))
                            cbc(ac, "BaseAmount", gross_value, **money_attrs(gross_price, currency))


            def convert_tree(root: ET.Element, profile_id: str | None = PEPPOL_BILLING_PROFILE_ID) -> ET.Element:
                exchanged = root.find("rsm:ExchangedDocument", CII_NS)
                invoice_type = text(exchanged, "ram:TypeCode") if exchanged is not None else None
                is_credit_note = invoice_type in INVOICE_TYPE_TO_CREDIT_NOTE
                root_ns = UBL_CREDIT_NOTE_NS if is_credit_note else UBL_INVOICE_NS
                root_tag = "CreditNote" if is_credit_note else "Invoice"
                type_tag = "CreditNoteTypeCode" if is_credit_note else "InvoiceTypeCode"

                if is_credit_note:
                    ET.register_namespace("", UBL_CREDIT_NOTE_NS)
                else:
                    ET.register_namespace("", UBL_INVOICE_NS)

                trx = find_trade_transaction(root)
                agreement = find_header_agreement(trx)
                delivery = find_header_delivery(trx)
                settlement = find_header_settlement(trx)
                currency = text(settlement, "ram:InvoiceCurrencyCode")

                out = ET.Element(q(root_ns, root_tag))
                cbc(out, "UBLVersionID", "2.1")
                cbc(out, "CustomizationID", CUSTOMIZATION_ID)
                cbc(out, "ProfileID", profile_id)
    ##
                #if profile_xml ==  PEPPOL3:
                #    cbc(out, "business_process_type_id", BUSINESS_PROCESS_TYPE_ID)
                #else: 
                    #if profile_id:                           
    #
                add_if_text(out, cbc, "ID", text(exchanged, "ram:ID") if exchanged is not None else None)
                add_if_text(out, cbc, "IssueDate", date_text(exchanged, "ram:IssueDateTime/udt:DateTimeString") if exchanged is not None else None)
                add_if_text(out, cbc, type_tag, invoice_type)
                add_if_text(out, cbc, "Note", text(exchanged, "ram:IncludedNote/ram:Content") if exchanged is not None else None)
                add_if_text(out, cbc, "DocumentCurrencyCode", currency)
                add_if_text(out, cbc, "TaxCurrencyCode", text(settlement, "ram:TaxCurrencyCode"))
                add_if_text(out, cbc, "BuyerReference", text(agreement, "ram:BuyerReference"))

                add_document_references(out, agreement)
                add_party(out, "AccountingSupplierParty", agreement.find("ram:SellerTradeParty", CII_NS) if agreement is not None else None)
                add_party(out, "AccountingCustomerParty", agreement.find("ram:BuyerTradeParty", CII_NS) if agreement is not None else None)
                add_delivery(out, delivery)
                add_payment(out, settlement)
                add_allowance_charges(out, settlement, currency)
                add_tax_total(out, settlement, currency)
                add_legal_monetary_total(out, settlement, currency, is_credit_note)
                add_lines(out, trx, currency, is_credit_note)
                return out


            def convert_file(input_file) -> ET.ElementTree:
                parser = ET.XMLParser()
                tree = ET.parse(input_file, parser=parser)
                converted = convert_tree(tree.getroot(), profile_id=PEPPOL_BILLING_PROFILE_ID)
                ET.indent(converted, space="  ")
                return ET.ElementTree(converted)


    ###########################################################
    # MAPPING             
            result = convert_file(input_file=Datendatei)
            
            buffer = ET.tostring(result.getroot(), encoding='utf-8', xml_declaration=True)   
            pre = "UBL_PEPPOL1_"
            if profile_xml == PEPPOL3: pre = "UBL_PEPPOL3_"
            data = {"df": buffer,"filename": f"{pre}{Datendatei.name}.xml", "mime": "application/xml"}
            

            return data

            
        except Exception as e:
            st.write(e)
            
            










