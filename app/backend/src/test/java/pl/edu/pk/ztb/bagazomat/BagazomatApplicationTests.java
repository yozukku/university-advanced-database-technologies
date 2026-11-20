package pl.edu.pk.ztb.bagazomat;

import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;
import pl.edu.pk.ztb.bagazomat.lockermat.Lockermat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** @author Anton Gorokh */
@Testcontainers
@SpringBootTest
class BagazomatApplicationTests {

	@Container
	@ServiceConnection
	static final PostgreSQLContainer postgres = new PostgreSQLContainer(
			DockerImageName.parse("bagazomat-postgres:17-postgis").asCompatibleSubstituteFor("postgres"));

	@Autowired
	private JdbcTemplate jdbc;

	@Autowired
	private EntityManager entityManager;

	@Test
	void migrationMatchesCanonicalSchema() throws IOException {
		byte[] canonical = Files.readAllBytes(Path.of("../../docs/design/schema.sql"));
		byte[] migration = Files.readAllBytes(Path.of("src/main/resources/db/migration/V1__schema.sql"));
		Assertions.assertArrayEquals(canonical, migration);
	}

	@Test
	@Transactional
	void readsLockerCoordinatesAfterFlywayAndValidation() {
		Long id = jdbc.queryForObject("""
				insert into lockermat_ (code_, name_, address_, location_)
				values ('KRK-TEST', 'Kraków Główny', 'Kraków', st_setsrid(st_makepoint(19.947, 50.068), 4326))
				returning id_
				""", Long.class);

		Lockermat locker = entityManager.find(Lockermat.class, id);

		Assertions.assertEquals(19.947, locker.getLng(), 0.000001);
		Assertions.assertEquals(50.068, locker.getLat(), 0.000001);
	}
}
