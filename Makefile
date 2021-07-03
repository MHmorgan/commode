
venv:
	python3 -m venv venv
	@echo "Now run:"
	@echo "	source venv/bin/activate"

requirements:
	python3 -m pip install -r requirements.txt

lint:
	pylint commode | tee lint.log
