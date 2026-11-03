FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY app.py /app/app.py
RUN mkdir /protected && echo "Protected demonstration file on VM2" > /protected/demo.txt && chmod 444 /protected/demo.txt
USER 10001:10001
EXPOSE 8000
CMD ["python", "app.py"]
