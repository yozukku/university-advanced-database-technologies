package pl.edu.pk.ztb.bagazomat;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Bean;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/** @author Anton Gorokh */
@TestConfiguration(proxyBeanMethods = false)
public class PostgresContainerConfiguration {

	@Bean
	@ServiceConnection
	PostgreSQLContainer postgres() {
		return new PostgreSQLContainer(DockerImageName.parse("bagazomat-postgres:17-postgis").asCompatibleSubstituteFor("postgres"));
	}
}
