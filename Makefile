.PHONY: docs tests

docs: docs.md

docs.md: proc.py README.md src/holmes_schema.py src/scandal_instances.py src/graph.py
	pdm run python proc.py README.md src/holmes_schema.py src/scandal_instances.py src/graph.py > docs.md

tests: tests.md

tests.md: proc.py tests/test_scandal.py
	pdm run python proc.py tests/test_scandal.py > tests.md
