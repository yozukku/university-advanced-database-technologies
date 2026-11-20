package pl.edu.pk.ztb.bagazomat.lockermat;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import org.springframework.transaction.annotation.Transactional;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import pl.edu.pk.ztb.bagazomat.TestRows;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.List;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@Import(PostgresContainerConfiguration.class)
class LockermatSearchTests {

	private static final String LOCKERMAT = "KRK-GLOWNY";

	private static final JsonMapper JSON = JsonMapper.builder()
			.enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
			.build();

	private static final String INSERT_LEG = """
			with cell as (select c.id_, c.size_
			              from lockermat_cell_ c
			                       join lockermat_ l on l.id_ = c.lockermat_id_
			              where l.code_ = ? and c.number_ = ?),
			     new_order as (insert into order_ (number_, customer_id_, type_, size_, tariff_id_, price_, payment_deadline_)
			                   select left(gen_random_uuid()::text, 20), u.id_, 'STORAGE', t.size_, t.id_, t.storage_price_per_day_, now() + interval '15 minutes'
			                   from customer_ u
			                            cross join tariff_ t
			                            join cell on cell.size_ = t.size_
			                   where u.keycloak_id_ = ?
			                   returning id_, size_)
			insert into reservation_ (order_id_, size_, cell_id_, leg_, from_, to_, status_, deposited_at_)
			select o.id_, o.size_, cell.id_, 'STORAGE', ?, ?, ?, case when ? = 'OCCUPIED' then cast(? as timestamptz) end
			from new_order o
			         cross join cell
			""";

	private final Instant from = Instant.now().plus(Duration.ofDays(1)).truncatedTo(ChronoUnit.SECONDS);
	private final Instant to = from.plus(Duration.ofHours(4));

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@Test
	void lowersFreeCountForOverlappingBookedLeg() throws Exception {
		long free = freeCells(CellSize.S);
		long freeMedium = freeCells(CellSize.M);

		insertLeg(1, "BOOKED", from.minus(Duration.ofHours(1)), from.plus(Duration.ofHours(1)));

		Assertions.assertEquals(free - 1, freeCells(CellSize.S));
		Assertions.assertEquals(freeMedium, freeCells(CellSize.M));
	}

	@Test
	void ignoresCancelledAndAdjacentLegs() throws Exception {
		long free = freeCells(CellSize.S);

		insertLeg(1, "CANCELLED", from, to);
		insertLeg(2, "BOOKED", from.minus(Duration.ofHours(3)), from);
		insertLeg(3, "BOOKED", to, to.plus(Duration.ofHours(3)));

		Assertions.assertEquals(free, freeCells(CellSize.S));
	}

	@Test
	void countsOverstayedCellAsTaken() throws Exception {
		long free = freeCells(CellSize.S);
		Instant now = Instant.now();

		insertLeg(4, "OCCUPIED", now.minus(Duration.ofHours(5)), now.minus(Duration.ofHours(1)));

		Assertions.assertEquals(free - 1, freeCells(CellSize.S));
	}

	@Test
	void excludesOutOfServiceCells() throws Exception {
		long free = freeCells(CellSize.L);

		jdbc.update("update lockermat_cell_ set status_ = 'OUT_OF_SERVICE' where number_ = 11 and lockermat_id_ = ?", lockermatId());

		Assertions.assertEquals(free - 1, freeCells(CellSize.L));
	}

	@Test
	void excludesSuspendedLockermats() throws Exception {
		jdbc.update("update lockermat_ set status_ = 'SUSPENDED' where code_ = ?", LOCKERMAT);

		List<Long> ids = search("", from, to).valueStream()
				.map(lockermat -> lockermat.path("id").asLong())
				.toList();

		Assertions.assertEquals(11, ids.size());
		Assertions.assertFalse(ids.contains(lockermatId()));
	}

	@Test
	void pricesStorageByStartedDays() throws Exception {
		Assertions.assertEquals(new BigDecimal("30.00"), price(CellSize.S, Duration.ofHours(25)));
		Assertions.assertEquals(new BigDecimal("15.00"), price(CellSize.S, Duration.ofHours(24)));
		Assertions.assertEquals(new BigDecimal("30.00"), price(CellSize.L, Duration.ofHours(4)));
	}

	@Test
	void searchesAddressAndNameInAddressOrder() throws Exception {
		Assertions.assertEquals(List.of("Rynek Główny", "Lotnisko Kraków-Balice", "Kraków Główny"), names(search("kraków", from, to)));
		Assertions.assertEquals(List.of("Lotnisko Gdańsk", "Lotnisko Kraków-Balice", "Lotnisko Chopina", "Lotnisko Wrocław"),
				names(search("LOTNISKO", from, to)));
		Assertions.assertEquals(List.of(), names(search("%", from, to)));
	}

	@Test
	void ordersSameAddressByName() throws Exception {
		jdbc.update("""
				insert into lockermat_ (code_, name_, address_, location_)
				values ('KRK-DWORZEC', 'Kraków Dworzec', 'Kraków, ul. Pawia 5a', 'SRID=4326;POINT(19.947886 50.068424)')
				""");

		Assertions.assertEquals(List.of("Kraków Dworzec", "Kraków Główny"), names(search("pawia", from, to)));
	}

	@Test
	void listsEverySizeOfEveryActiveLockermat() throws Exception {
		JsonNode lockermats = search("", from, to);

		Assertions.assertEquals(12, lockermats.size());
		for (JsonNode lockermat : lockermats) {
			Assertions.assertEquals(List.of("S", "M", "L"), lockermat.path("sizes").valueStream().map(size -> size.path("size").asString()).toList());
		}
	}

	@Test
	void rejectsEmptyWindowAndMissingBound() throws Exception {
		assertBadRequest(request("", from, from));
		assertBadRequest(MockMvcRequestBuilders.get("/api/lockermats").param("from", from.toString()));
		assertBadRequest(MockMvcRequestBuilders.get("/api/lockermats").param("from", "jutro").param("to", to.toString()));
	}

	private long freeCells(CellSize size) throws Exception {
		return sizeOf(size, search("", from, to)).path("free").asLong();
	}

	private BigDecimal price(CellSize size, Duration duration) throws Exception {
		return sizeOf(size, search("", from, from.plus(duration))).path("price").decimalValue();
	}

	private JsonNode sizeOf(CellSize size, JsonNode lockermats) {
		long id = lockermatId();
		JsonNode lockermat = lockermats.valueStream()
				.filter(candidate -> candidate.path("id").asLong() == id)
				.findFirst()
				.orElseThrow();
		return lockermat.path("sizes").valueStream()
				.filter(candidate -> candidate.path("size").asString().equals(size.name()))
				.findFirst()
				.orElseThrow();
	}

	private List<String> names(JsonNode lockermats) {
		return lockermats.valueStream()
				.map(lockermat -> lockermat.path("name").asString())
				.toList();
	}

	private JsonNode search(String query, Instant windowFrom, Instant windowTo) throws Exception {
		String body = mockMvc.perform(asAnna(request(query, windowFrom, windowTo)))
				.andExpect(MockMvcResultMatchers.status().isOk())
				.andReturn()
				.getResponse()
				.getContentAsString(StandardCharsets.UTF_8);
		return JSON.readTree(body);
	}

	private MockHttpServletRequestBuilder request(String query, Instant windowFrom, Instant windowTo) {
		return MockMvcRequestBuilders.get("/api/lockermats")
				.param("q", query)
				.param("from", windowFrom.toString())
				.param("to", windowTo.toString());
	}

	private void assertBadRequest(MockHttpServletRequestBuilder request) throws Exception {
		String body = mockMvc.perform(asAnna(request))
				.andExpect(MockMvcResultMatchers.status().is(HttpStatus.BAD_REQUEST.value()))
				.andReturn()
				.getResponse()
				.getContentAsString(StandardCharsets.UTF_8);
		Assertions.assertEquals("BAD_REQUEST", JSON.readTree(body).path("code").asString(), body);
	}

	private MockHttpServletRequestBuilder asAnna(MockHttpServletRequestBuilder request) {
		return request.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(TestRows.ANNA.toString())));
	}

	private void insertLeg(int cellNumber, String status, Instant legFrom, Instant legTo) {
		jdbc.update(INSERT_LEG, LOCKERMAT, cellNumber, TestRows.ANNA, legFrom.atOffset(ZoneOffset.UTC), legTo.atOffset(ZoneOffset.UTC), status, status,
				legFrom.atOffset(ZoneOffset.UTC));
	}

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}
}
