FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
COPY requirements.lock /r.lock
# (proxy CA lines only needed inside this sandbox)
# COPY ca-bundle.crt /ca.crt
# ENV PIP_CERT=/ca.crt
RUN pip install -q -r /r.lock
ENV PYTHONPATH=/sqlglot SKIP_INTEGRATION=0
WORKDIR /sqlglot
