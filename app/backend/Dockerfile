FROM eclipse-temurin:21-jdk-jammy@sha256:a8b6e4da662e2ff710459e76be515a14746045c7a7493531d0901ca10a231501 AS build
WORKDIR /build
COPY mvnw pom.xml ./
COPY .mvn .mvn
COPY src/main src/main
RUN ./mvnw -B -ntp -Dmaven.test.skip=true package

FROM eclipse-temurin:21-jre-jammy@sha256:f1ad2fff1437cbcf7be96408f264ad5d2128fad9cf262f88f1827a84e60d246e
WORKDIR /app
COPY --from=build /build/target/bagazomat-*.jar app.jar
USER 10001:10001
ENTRYPOINT ["java", "-jar", "app.jar"]
