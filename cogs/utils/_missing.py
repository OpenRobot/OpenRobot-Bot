from typing import Any


class _Missing:
	def __eq__(self, other):
		return isinstance(other, _Missing)

	def __bool__(self):
		return False

	def __hash__(self):
		return 0

	def __repr__(self):
		return '...'


MISSING: Any = _Missing()