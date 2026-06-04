.PHONY: docs

docs: docs.md

docs.md: proc.py README.md src/holmes_schema.py src/scandal_instances.py
	pdm run python proc.py README.md src/holmes_schema.py src/scandal_instances.py > docs.md
