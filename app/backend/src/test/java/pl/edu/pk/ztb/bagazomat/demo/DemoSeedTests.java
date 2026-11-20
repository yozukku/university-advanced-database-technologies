package pl.edu.pk.ztb.bagazomat.demo;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/** @author Anton Gorokh */
@SpringBootTest
@Import(PostgresContainerConfiguration.class)
class DemoSeedTests {

	private static final Map<String, CityBox> CITY_BOXES = Map.of(
			"Kraków", new CityBox(19.70, 20.25, 49.95, 50.13),
			"Warszawa", new CityBox(20.85, 21.28, 52.09, 52.37),
			"Gdańsk", new CityBox(18.42, 18.95, 54.27, 54.45),
			"Wrocław", new CityBox(16.80, 17.18, 51.04, 51.22));

	@Autowired
	private JdbcTemplate jdbc;

	@Test
	void placesTwelveLockersInsideTheirCities() {
		List<Locker> lockers = jdbc.query("""
				select split_part(address_, ', ', 1) as city_, st_x(location_) as lng_, st_y(location_) as lat_
				from lockermat_
				where status_ = 'ACTIVE' and time_zone_ = 'Europe/Warsaw'
				""", (row, number) -> new Locker(row.getString("city_"), row.getDouble("lng_"), row.getDouble("lat_")));

		Assertions.assertEquals(12, lockers.size());
		Assertions.assertEquals(CITY_BOXES.keySet(), lockers.stream().map(Locker::city).collect(Collectors.toSet()));
		for (Locker locker : lockers) {
			Assertions.assertTrue(locker.lng() < locker.lat(), locker::toString);
			Assertions.assertTrue(CITY_BOXES.get(locker.city()).contains(locker), locker::toString);
		}
	}

	@Test
	void givesEveryLockerTwelveCellsWithoutOpeningHours() {
		List<String> layouts = jdbc.queryForList("""
				select string_agg(c.size_, '' order by c.number_)
				from lockermat_ l
				         join lockermat_cell_ c on c.lockermat_id_ = l.id_ and c.status_ = 'IN_SERVICE'
				group by l.id_
				""", String.class);

		Assertions.assertEquals(144, jdbc.queryForObject("select count(*) from lockermat_cell_", Integer.class));
		Assertions.assertEquals(List.of("SSSSSSMMMMLL"), layouts.stream().distinct().toList());
		Assertions.assertEquals(0, jdbc.queryForObject("select count(*) from lockermat_opening_hours_", Integer.class));
	}

	@Test
	void opensOneTariffPerSize() {
		List<String> tariffs = jdbc.queryForList("""
				select concat_ws(' ', size_, storage_price_per_day_, shipment_price_, overstay_price_per_day_)
				from tariff_
				where valid_to_ is null and valid_from_ <= now()
				order by storage_price_per_day_
				""", String.class);

		Assertions.assertEquals(List.of("S 15.00 39.00 20.00", "M 20.00 49.00 25.00", "L 30.00 59.00 35.00"), tariffs);
		Assertions.assertEquals(3, jdbc.queryForObject("select count(*) from tariff_", Integer.class));
	}

	@Test
	void registersRealmUsersAndOneDemoSender() {
		JsonNode users = JsonMapper.shared().readTree(Path.of("../keycloak/realm-bagazomat.json")).path("users");

		for (JsonNode user : users) {
			Map<String, Object> customer = jdbc.queryForMap("select phone_, terms_version_ from customer_ where keycloak_id_ = ?",
					UUID.fromString(user.path("id").asString()));
			Assertions.assertEquals(user.path("attributes").path("phoneNumber").path(0).asString(), customer.get("phone_"));
			Assertions.assertEquals("demo-1", customer.get("terms_version_"));
		}
		Assertions.assertEquals(users.size() + 1, jdbc.queryForObject("select count(*) from customer_", Integer.class));
		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*) from customer_ where phone_ is null and company_name_ = 'Nadawca demonstracyjny' and terms_version_ = 'demo-1'
				""", Integer.class));
	}

	private record Locker(String city, double lng, double lat) {
	}

	private record CityBox(double minLng, double maxLng, double minLat, double maxLat) {

		boolean contains(Locker locker) {
			return locker.lng() >= minLng && locker.lng() <= maxLng && locker.lat() >= minLat && locker.lat() <= maxLat;
		}
	}
}
