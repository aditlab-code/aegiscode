"""Modul penagihan dan faktur untuk pengujian mock repository."""

from typing import List, Dict, Any, Optional


class InvoiceService:
    """Layanan pengelolaan faktur dan kalkulasi diskon pelanggan."""

    def __init__(self, tax_rate: float = 0.11) -> None:
        self.tax_rate = tax_rate

    def calculate_total(self, items: List[Dict[str, Any]], discount: float = 0.0) -> float:
        """Hitung total faktur dengan penyesuaian diskon dan tarif pajak."""
        subtotal = sum(float(item.get("price", 0.0)) * int(item.get("qty", 1)) for item in items)
        discounted = max(0.0, subtotal - discount)
        total = discounted * (1.0 + self.tax_rate)
        return round(total, 2)

    def validate_invoice(self, invoice_id: str) -> bool:
        """Validasi format identifier faktur pelanggan."""
        if not invoice_id:
            return False
        return invoice_id.startswith("INV-") and len(invoice_id) >= 8


def generate_extended_audit_log(events: List[Dict[str, Any]]) -> str:
    """Fungsi panjang untuk menguji pemotongan potongan kode berukuran besar (> 1.800 karakter).

    Fungsi ini sengaja memuat blok kode berulang yang panjang agar pemecah potongan
    membagi fungsi menjadi beberapa sub-potongan dengan nomor baris yang valid.
    """
    lines = []
    lines.append("=== BEGIN AUDIT TRAIL LOG GENERATION ===")
    for idx, event in enumerate(events):
        event_type = event.get("type", "UNKNOWN")
        actor = event.get("actor", "system")
        timestamp = event.get("timestamp", "1970-01-01T00:00:00Z")
        status = event.get("status", "SUCCESS")
        details = event.get("details", "")
        formatted_entry = (
            f"[ENTRY #{idx + 1:04d}] TS={timestamp} | TYPE={event_type} | ACTOR={actor} | "
            f"STATUS={status} | SUMMARY={details}"
        )
        lines.append(formatted_entry)
        # Menambahkan bantalan string panjang agar total karakter melebihi 2.000 karakter
        padding = (
            f"AUDIT_RECORD_METADATA_EXTENDED_TRACE_ID_{idx:05d}_HASH_HEX_VERIFICATION_CHECK_"
            f"STATUS_OK_CORRELATION_ID_XYZ_{idx * 1000}"
        )
        lines.append(f"    METADATA: {padding}")
        lines.append(f"    VALIDATION: Checksum verified for record #{idx + 1}")
        lines.append(f"    SECURITY: Signature valid for actor {actor}")
        lines.append(f"    COMPLIANCE: Retained according to statutory data retention policy")
        lines.append(f"    INFRASTRUCTURE: Cloud node host ip 10.0.{idx % 255}.1 in cluster us-east-prod")
        lines.append(f"    DIAGNOSTICS: Network latency 1.45ms, memory pressure nominal, thread worker pool green")
        lines.append(f"    AUTHORIZATION: RBAC token scopes verified [read:billing, write:audit, execute:reconciliation]")
        lines.append(f"    OBSERVABILITY: Distributed trace context exported via OpenTelemetry OTLP grpc exporter")
        lines.append(f"    ENCRYPTION: Payload sealed with AES-256-GCM hardware accelerated cipher instructions")


    lines.append("=== END AUDIT TRAIL LOG GENERATION ===")
    return "\n".join(lines)
