from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Protocol


class LineWithQuantity(Protocol):
    quantity: object
    unit_of_measure: str | None


@dataclass(frozen=True)
class UnitSpec:
    code: str
    dimension: str
    factor_to_base: Decimal
    base_code: str


@dataclass(frozen=True)
class QuantityProfile:
    quantity: Decimal
    dimension: str | None
    unit: str | None
    compatible: bool
    source_units: tuple[str, ...]


_ALIASES = {
    "PZ": "EA",
    "PZA": "EA",
    "PCE": "EA",
    "PCS": "EA",
    "PC": "EA",
    "UNIT": "EA",
    "UNITA": "EA",
    "UN": "EA",
    "NR": "EA",
    "PEZZI": "EA",
    "KGS": "KG",
    "KILOGRAM": "KG",
    "KILOGRAMMO": "KG",
    "KILOGRAMMI": "KG",
    "GRAMMO": "G",
    "GRAMMI": "G",
    "LITRO": "L",
    "LITRI": "L",
    "LTR": "L",
    "MILLILITRO": "ML",
    "MILLILITRI": "ML",
    "METRO": "M",
    "METRI": "M",
    "CENTIMETRO": "CM",
    "CENTIMETRI": "CM",
    "MILLIMETRO": "MM",
    "MILLIMETRI": "MM",
    "ORA": "H",
    "ORE": "H",
    "HOUR": "H",
    "HOURS": "H",
    "MINUTO": "MIN",
    "MINUTI": "MIN",
}

_SPECS = {
    "EA": UnitSpec("EA", "count", Decimal("1"), "EA"),
    "KG": UnitSpec("KG", "mass", Decimal("1"), "KG"),
    "G": UnitSpec("G", "mass", Decimal("0.001"), "KG"),
    "MG": UnitSpec("MG", "mass", Decimal("0.000001"), "KG"),
    "T": UnitSpec("T", "mass", Decimal("1000"), "KG"),
    "L": UnitSpec("L", "volume", Decimal("1"), "L"),
    "CL": UnitSpec("CL", "volume", Decimal("0.01"), "L"),
    "ML": UnitSpec("ML", "volume", Decimal("0.001"), "L"),
    "M": UnitSpec("M", "length", Decimal("1"), "M"),
    "CM": UnitSpec("CM", "length", Decimal("0.01"), "M"),
    "MM": UnitSpec("MM", "length", Decimal("0.001"), "M"),
    "M2": UnitSpec("M2", "area", Decimal("1"), "M2"),
    "CM2": UnitSpec("CM2", "area", Decimal("0.0001"), "M2"),
    "MM2": UnitSpec("MM2", "area", Decimal("0.000001"), "M2"),
    "M3": UnitSpec("M3", "volume_spatial", Decimal("1"), "M3"),
    "CM3": UnitSpec("CM3", "volume_spatial", Decimal("0.000001"), "M3"),
    "H": UnitSpec("H", "time", Decimal("1"), "H"),
    "MIN": UnitSpec("MIN", "time", Decimal("0.0166666666666666666666666667"), "H"),
}


def decimal_value(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def normalize_uom(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", str(value).upper().strip())
    if not normalized:
        return None
    return _ALIASES.get(normalized, normalized)


def unit_spec(value: str | None) -> UnitSpec | None:
    code = normalize_uom(value)
    if code is None:
        return None
    known = _SPECS.get(code)
    if known:
        return known
    return UnitSpec(code, f"custom:{code}", Decimal("1"), code)


def quantity_profile(lines: Iterable[LineWithQuantity]) -> QuantityProfile:
    materialized = list(lines)
    if not materialized:
        return QuantityProfile(Decimal("0"), None, None, True, ())
    specs = [unit_spec(line.unit_of_measure) for line in materialized]
    source_units = tuple(sorted({spec.code for spec in specs if spec is not None}))
    if all(spec is None for spec in specs):
        return QuantityProfile(
            sum((decimal_value(line.quantity) for line in materialized), Decimal("0")),
            None,
            None,
            True,
            (),
        )
    if any(spec is None for spec in specs):
        return QuantityProfile(
            sum((decimal_value(line.quantity) for line in materialized), Decimal("0")),
            None,
            None,
            False,
            source_units,
        )
    concrete = [spec for spec in specs if spec is not None]
    dimensions = {spec.dimension for spec in concrete}
    if len(dimensions) != 1:
        return QuantityProfile(
            sum((decimal_value(line.quantity) for line in materialized), Decimal("0")),
            None,
            None,
            False,
            source_units,
        )
    quantity = sum(
        (decimal_value(line.quantity) * spec.factor_to_base for line, spec in zip(materialized, concrete, strict=True)),
        Decimal("0"),
    )
    return QuantityProfile(quantity, concrete[0].dimension, concrete[0].base_code, True, source_units)


def profiles_compatible(left: QuantityProfile, right: QuantityProfile) -> bool:
    if not left.compatible or not right.compatible:
        return False
    if left.dimension is None and right.dimension is None:
        return True
    return left.dimension == right.dimension


def canonical_unit_price(unit_price: object, price_base_quantity: object, unit_of_measure: str | None) -> Decimal:
    base_quantity = decimal_value(price_base_quantity) or Decimal("1")
    price_per_source_unit = decimal_value(unit_price) / base_quantity
    spec = unit_spec(unit_of_measure)
    if spec is None:
        return price_per_source_unit
    return price_per_source_unit / spec.factor_to_base
