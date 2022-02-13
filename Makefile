
lint:
	pylint commode | tee lint.log

upload:
	python3 setup.py sdist
	twine upload dist/*

# Use homebrew-pypi-poet to create/update homebrew formula
poet:
	poet -f commode
