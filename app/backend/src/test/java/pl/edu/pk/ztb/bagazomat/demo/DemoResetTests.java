package pl.edu.pk.ztb.bagazomat.demo;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;

import java.util.List;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("dev")
@Import(PostgresContainerConfiguration.class)
class DemoResetTests {

	private static final List<String> ORDER_TABLES = List.of(
			"order_", "reservation_", "shipment_", "payment_", "access_code_", "incident_", "cell_opening_", "audit_event_");

	private static final String INSERT_ORDERS = """
			insert into order_ (number_, customer_id_, type_, size_, tariff_id_, price_, payment_deadline_)
			select 'TEST-1', c.id_, 'STORAGE', t.size_, t.id_, t.storage_price_per_day_, now() + interval '15 minutes'
			from customer_ c
			         cross join tariff_ t
			where c.keycloak_id_ = '900f9895-3b4d-5e82-a35f-ad11c64f9f00' and t.size_ = 'S';
			insert into reservation_ (order_id_, size_, cell_id_, leg_, from_, to_)
			select currval('order_id_seq_'), 'S', min(id_), 'STORAGE', now() + interval '1 hour', now() + interval '5 hours'
			from lockermat_cell_
			where size_ = 'S';
			insert into access_code_ (reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_)
			values (currval('reservation_id_seq_'), 'DROP_OFF', sha256('test'), now() + interval '1 hour', now() + interval '5 hours');
			insert into cell_opening_ (access_code_id_, channel_, actor_keycloak_id_, result_)
			values (currval('access_code_id_seq_'), 'APP', '900f9895-3b4d-5e82-a35f-ad11c64f9f00', 'PENDING');
			insert into payment_ (order_id_, kind_, amount_, provider_)
			values (currval('order_id_seq_'), 'CHARGE', 15.00, 'MOCK');
			insert into incident_ (cell_id_, reservation_id_, order_id_, source_, type_, description_)
			select cell_id_, id_, order_id_, 'CUSTOMER', 'OTHER', 'Test'
			from reservation_
			where id_ = currval('reservation_id_seq_');
			insert into order_ (number_, customer_id_, type_, size_, tariff_id_, price_, payment_deadline_)
			select 'TEST-2', c.id_, 'SHIPMENT', t.size_, t.id_, t.shipment_price_, now() + interval '15 minutes'
			from customer_ c
			         cross join tariff_ t
			where c.keycloak_id_ = '95912bb7-ca81-5398-b494-078466a4edd2' and t.size_ = 'M';
			insert into shipment_ (order_id_, recipient_name_, recipient_phone_, declared_value_)
			values (currval('order_id_seq_'), 'Jan Nowak', '+48500100300', 100.00);
			insert into audit_event_ (entity_, entity_id_, action_, actor_, changes_)
			values ('ORDER', currval('order_id_seq_'), 'ORDER_CREATED', '{"kind": "SYSTEM", "job": "test"}', '[]');
			""";

	private static final String SEED_FINGERPRINT = """
			select md5(concat_ws('|',
			                     (select string_agg(l::text, ',' order by l.id_) from lockermat_ l),
			                     (select string_agg(c::text, ',' order by c.id_) from lockermat_cell_ c),
			                     (select string_agg(t::text, ',' order by t.id_) from tariff_ t),
			                     (select string_agg(u::text, ',' order by u.id_) from customer_ u)))
			""";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@Test
	void emptiesOrderTablesAndKeepsSeed() throws Exception {
		String seed = jdbc.queryForObject(SEED_FINGERPRINT, String.class);
		jdbc.execute(INSERT_ORDERS);
		ORDER_TABLES.forEach(table -> Assertions.assertNotEquals(0, countRows(table), table));

		mockMvc.perform(MockMvcRequestBuilders.post("/api/dev/reset")
						.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject("a4bba234-ddf1-5dbc-bf7d-fca171bfe08f")))
						.with(SecurityMockMvcRequestPostProcessors.csrf()))
				.andExpect(MockMvcResultMatchers.status().isNoContent());

		ORDER_TABLES.forEach(table -> Assertions.assertEquals(0, countRows(table), table));
		Assertions.assertEquals(seed, jdbc.queryForObject(SEED_FINGERPRINT, String.class));
		Assertions.assertEquals(List.of(12, 144, 3, 3), List.of(countRows("lockermat_"), countRows("lockermat_cell_"), countRows("tariff_"), countRows("customer_")));
	}

	private int countRows(String table) {
		return jdbc.queryForObject("select count(*) from " + table, Integer.class);
	}
}
