FROM eclipse-temurin:17-jre-jammy

WORKDIR /app

COPY app.jar /app/app.jar
RUN mkdir -p /data /opt/crosshub/python

ENV SPRING_PROFILES_ACTIVE=prod
ENV CROSSHUB_DB_PATH=/data/crosshub.db
ENV CROSSHUB_CRAWLER_USE_AGENT=true
ENV CROSSHUB_PYTHON=python3
ENV CROSSHUB_PYTHON_DIR=/opt/crosshub/python
ENV TEMU_PROFILE_ROOT=/data/temu-browser-profile
ENV TEMU_HEADLESS=1
ENV TEMU_BROWSER_CHANNEL=

EXPOSE 18080
ENTRYPOINT ["java", "-jar", "/app/app.jar", "--server.port=18080"]
