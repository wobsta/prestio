# Plone REST API IO tool

dump and load content from and to a Plone instance

## Installation

```python
pip install prestio
```

## Usage

```bash
# dump content to local directory:
prestio --password admin dump http://127.0.0.1:8080/Plone/muster .

# load content into plone instance:
prestio --password admin load work http://127.0.0.1:8080/Plone
```

