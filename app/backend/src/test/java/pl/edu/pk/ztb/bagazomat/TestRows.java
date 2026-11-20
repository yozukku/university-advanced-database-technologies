package pl.edu.pk.ztb.bagazomat;

import org.springframework.jdbc.core.JdbcTemplate;
import pl.edu.pk.ztb.bagazomat.lockermat.CellSize;
import pl.edu.pk.ztb.bagazomat.order.Order;
import pl.edu.pk.ztb.bagazomat.order.Reservation;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

/** @author Anton Gorokh */
public final class TestRows {

	public static final UUID ANNA = UUID.fromString("900f9895-3b4d-5e82-a35f-ad11c64f9f00");

	private TestRows() {
	}

	public static Order order(JdbcTemplate jdbc, String number, Order.Type type) {
		Long customerId = jdbc.queryForObject("select id_ from customer_ where keycloak_id_ = ?", Long.class, ANNA);
		Long tariffId = jdbc.queryForObject("select id_ from tariff_ where size_ = 'S'", Long.class);
		return new Order(number, customerId, type, CellSize.S, tariffId, new BigDecimal("15.00"), Instant.now().plus(Duration.ofMinutes(15)));
	}

	public static Reservation storageLeg(JdbcTemplate jdbc, Order order, Instant from, Instant to) {
		Long cellId = jdbc.queryForObject("select min(id_) from lockermat_cell_ where size_ = 'S'", Long.class);
		return new Reservation(order.getId(), CellSize.S, cellId, Reservation.Leg.STORAGE, from, to);
	}
}
