package pl.edu.pk.ztb.bagazomat.demo;

import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** @author Anton Gorokh */
@Service
@Profile("dev")
class DemoService {

	private static final String TRUNCATE_ORDERS = """
			truncate order_, reservation_, shipment_, payment_, access_code_, incident_, cell_opening_, audit_event_
			""";

	private final JdbcTemplate jdbc;

	DemoService(JdbcTemplate jdbc) {
		this.jdbc = jdbc;
	}

	void reset() {
		jdbc.execute(TRUNCATE_ORDERS);
	}
}
