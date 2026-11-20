package pl.edu.pk.ztb.bagazomat.lockermat;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

import java.math.BigDecimal;
import java.time.Instant;

/** @author Anton Gorokh */
@Entity
@Immutable
@Table(name = "tariff_")
public class Tariff {

	@Id
	@Column(name = "id_")
	private Long id;

	@Enumerated(EnumType.STRING)
	@Column(name = "size_", nullable = false, length = 10)
	private CellSize size;

	@Column(name = "valid_from_", nullable = false)
	private Instant validFrom;

	@Column(name = "valid_to_")
	private Instant validTo;

	@Column(name = "storage_price_per_day_", nullable = false, precision = 8, scale = 2)
	private BigDecimal storagePricePerDay;

	@Column(name = "shipment_price_", nullable = false, precision = 8, scale = 2)
	private BigDecimal shipmentPrice;

	@Column(name = "overstay_price_per_day_", nullable = false, precision = 8, scale = 2)
	private BigDecimal overstayPricePerDay;

	protected Tariff() {
	}
}
