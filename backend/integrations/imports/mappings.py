import re

from rest_framework import serializers


DATASET_SPECS = {
    "products": {
        "required": ("name", "sku", "category"),
        "aliases": {
            "name": ("name", "product name", "item", "item name", "product"),
            "sku": ("sku", "stock code", "product code", "item code", "code"),
            "category": ("category", "product category", "item category"),
            "brand": ("brand", "manufacturer", "make"),
            "unit": ("unit", "unit of measure", "uom"),
            "productType": ("product type", "type", "item type"),
            "openingStock": ("opening stock", "initial stock", "starting stock", "stock", "quantity"),
            "lowStockLevel": ("low stock level", "low stock", "reorder level", "minimum stock"),
            "costPrice": ("cost price", "cost", "buying price", "purchase price", "unit cost"),
            "sellingPrice": ("selling price", "sale price", "price", "retail price"),
            "designCode": ("design code", "design number", "design no", "tile design"),
            "size": ("size", "product size", "tile size"),
            "finish": ("finish", "tile finish"),
            "color": ("color", "colour"),
            "batchNumber": ("batch number", "batch no", "batch"),
            "piecesPerBox": ("pieces per box", "pcs per box", "pieces box"),
            "sqmPerBox": ("sqm per box", "square metres per box", "square meters per box", "m2 per box"),
            "loosePieces": ("loose pieces", "loose pcs"),
            "styleCode": ("style code", "style number", "style no"),
        },
    },
    "customers": {
        "required": ("name", "phone"),
        "aliases": {
            "name": ("name", "customer", "customer name", "full name"),
            "phone": ("phone", "phone number", "mobile", "mobile number", "contact"),
            "email": ("email", "email address"),
            "address": ("address", "customer address", "location"),
        },
    },
    "suppliers": {
        "required": ("name",),
        "aliases": {
            "name": ("name", "supplier", "supplier name", "vendor", "vendor name"),
            "phone": ("phone", "phone number", "mobile", "contact"),
            "email": ("email", "email address"),
            "address": ("address", "supplier address", "location"),
            "notes": ("notes", "note", "remarks", "comment"),
        },
    },
    "branch_inventory": {
        "required": ("sku", "stock"),
        "aliases": {
            "sku": ("sku", "stock code", "product code", "item code", "code"),
            "stock": ("stock", "quantity", "current stock", "stock quantity", "on hand"),
        },
    },
}


def _header_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def build_header_mapping(dataset, headers):
    spec = DATASET_SPECS.get(dataset)
    if not spec:
        raise serializers.ValidationError({"dataset": "Unsupported import dataset."})

    alias_lookup = {}
    for field, aliases in spec["aliases"].items():
        for alias in aliases:
            alias_lookup[_header_key(alias)] = field
        alias_lookup[_header_key(field)] = field

    columns = []
    unknown = []
    seen_fields = {}
    for index, header in enumerate(headers):
        field = alias_lookup.get(_header_key(header))
        if not field:
            unknown.append(header)
            continue
        if field in seen_fields:
            raise serializers.ValidationError(
                {
                    "file": (
                        f"Columns '{seen_fields[field]}' and '{header}' both map to "
                        f"'{field}'. Keep only one of them."
                    )
                }
            )
        seen_fields[field] = header
        columns.append({"index": index, "source": header, "field": field})

    missing = [field for field in spec["required"] if field not in seen_fields]
    if missing:
        raise serializers.ValidationError(
            {"file": "Missing required column(s): " + ", ".join(missing) + "."}
        )

    public_mapping = {
        "columns": [
            {"source": item["source"], "field": item["field"]}
            for item in columns
        ],
        "unknownHeaders": unknown,
        "requiredFields": list(spec["required"]),
    }
    return public_mapping, columns


def map_rows(rows, columns):
    mapped = []
    for row in rows:
        mapped.append(
            {
                item["field"]: (row[item["index"]] if item["index"] < len(row) else "")
                for item in columns
            }
        )
    return mapped
