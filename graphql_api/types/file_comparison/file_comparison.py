from typing import Optional

from ariadne import ObjectType

from services.comparison import FileComparison

file_comparison_bindable = ObjectType("FileComparison")


@file_comparison_bindable.field("baseName")
def resolve_base_name(file_comparison: FileComparison, info) -> Optional[str]:
    return file_comparison.name["base"]


@file_comparison_bindable.field("headName")
def resolve_head_name(file_comparison: FileComparison, info) -> Optional[str]:
    return file_comparison.name["head"]


@file_comparison_bindable.field("isNewFile")
def resolve_is_new_file(file_comparison: FileComparison, info) -> bool:
    base_name = file_comparison.name["base"]
    head_name = file_comparison.name["head"]
    return base_name is None and head_name is not None


@file_comparison_bindable.field("baseTotals")
def resolve_base_totals(file_comparison: FileComparison, info) -> dict:
    return file_comparison.totals["base"]


@file_comparison_bindable.field("headTotals")
def resolve_head_totals(file_comparison: FileComparison, info) -> dict:
    return file_comparison.totals["head"]