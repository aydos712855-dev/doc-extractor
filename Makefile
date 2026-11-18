eval:
	python eval.py

eval-mock:
	python eval.py --mock

extract:
	python -m src.cli $(FILE)

install:
	pip install -r requirements.txt
