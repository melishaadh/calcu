FROM python:3.12-slim

WORKDIR /app

COPY index.html style.css app.js config.js entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

EXPOSE 80

CMD ["/app/entrypoint.sh"]
