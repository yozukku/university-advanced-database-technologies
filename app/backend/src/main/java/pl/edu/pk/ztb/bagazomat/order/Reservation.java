package pl.edu.pk.ztb.bagazomat.order;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import pl.edu.pk.ztb.bagazomat.lockermat.CellSize;

import java.time.Instant;

/** @author Anton Gorokh */
@Entity
@Table(name = "reservation_")
public class Reservation {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "reservation_id")
	@SequenceGenerator(name = "reservation_id", sequenceName = "reservation_id_seq_", allocationSize = 1)
	@Column(name = "id_")
	private Long id;

	@Column(name = "order_id_", nullable = false)
	private Long orderId;

	@Enumerated(EnumType.STRING)
	@Column(name = "size_", nullable = false, length = 10)
	private CellSize size;

	@Column(name = "cell_id_", nullable = false)
	private Long cellId;

	@Enumerated(EnumType.STRING)
	@Column(name = "leg_", nullable = false, length = 16)
	private Leg leg;

	@Column(name = "from_", nullable = false)
	private Instant from;

	@Column(name = "to_", nullable = false)
	private Instant to;

	@Enumerated(EnumType.STRING)
	@Column(name = "status_", nullable = false, length = 16)
	private Status status = Status.BOOKED;

	@Column(name = "deposited_at_")
	private Instant depositedAt;

	@Column(name = "collected_at_")
	private Instant collectedAt;

	protected Reservation() {
	}

	public Reservation(Long orderId, CellSize size, Long cellId, Leg leg, Instant from, Instant to) {
		this.orderId = orderId;
		this.size = size;
		this.cellId = cellId;
		this.leg = leg;
		this.from = from;
		this.to = to;
	}

	public Long getId() {
		return id;
	}

	public enum Leg {
		STORAGE, ORIGIN, DESTINATION
	}

	public enum Status {
		BOOKED, OCCUPIED, COMPLETED, CANCELLED, NO_SHOW
	}
}
