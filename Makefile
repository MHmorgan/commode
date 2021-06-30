PYTHON=python3.8

venv:
	${PYTHON} -m venv venv
	@echo "Now run:"
	@echo "	source venv/bin/activate"

requirements:
	${PYTHON} -m pip install --user -r requirements.txt

lint:
	pylint louis | tee lint.log
