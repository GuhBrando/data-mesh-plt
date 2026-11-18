"""Values a stored data contract can hold. Pure, no I/O.

The ODCS mapper reads these; the API schemas spell them out as Literals, and a
test keeps the two in step, so adding a value cannot reach only one of them.
"""

CONTRACT_STATUSES = ("draft", "in_review", "active", "deprecated")
FIELD_TYPES = ("string", "integer", "float", "boolean", "date", "timestamp")
