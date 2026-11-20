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
import org.hibernate.annotations.Generated;
import pl.edu.pk.ztb.bagazomat.lockermat.CellSize;

import java.math.BigDecimal;
import java.time.Instant;

/** @author Anton Gorokh */
@Entity
@Table(name = "order_")
public class Order {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "order_id")
	@SequenceGenerator(name = "order_id", sequenceName = "order_id_seq_", allocationSize = 1)
	@Column(name = "id_")
	private Long id;

	@Column(name = "number_", nullable = false, length = 20)
	private String number;

	@Column(name = "customer_id_", nullable = false)
	private Long customerId;

	@Enumerated(EnumType.STRING)
	@Column(name = "type_", nullable = false, length = 16)
	private Type type;

	@Enumerated(EnumType.STRING)
	@Column(name = "size_", nullable = false, length = 10)
	private CellSize size;

	@Column(name = "tariff_id_", nullable = false)
	private Long tariffId;

	@Enumerated(EnumType.STRING)
	@Column(name = "status_", nullable = false, length = 16)
	private Status status = Status.AWAITING_PAYMENT;

	@Column(name = "price_", nullable = false, precision = 10, scale = 2)
	private BigDecimal price;

	@Column(name = "payment_deadline_", nullable = false)
	private Instant paymentDeadline;

	@Generated
	@Column(name = "created_at_", nullable = false, updatable = false)
	private Instant createdAt;

	@Column(name = "closed_at_")
	private Instant closedAt;

	protected Order() {
	}

	public Order(String number, Long customerId, Type type, CellSize size, Long tariffId, BigDecimal price, Instant paymentDeadline) {
		this.number = number;
		this.customerId = customerId;
		this.type = type;
		this.size = size;
		this.tariffId = tariffId;
		this.price = price;
		this.paymentDeadline = paymentDeadline;
	}

	public Long getId() {
		return id;
	}

	public enum Type {
		STORAGE, SHIPMENT
	}

	public enum Status {
		AWAITING_PAYMENT, PAID, COMPLETED, CANCELLED, EXPIRED
	}
}
