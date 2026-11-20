package pl.edu.pk.ztb.bagazomat.lockermat;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Formula;
import org.hibernate.annotations.Immutable;

import java.time.Instant;

/** @author Anton Gorokh */
@Entity
@Immutable
@Table(name = "lockermat_")
public class Lockermat {

	@Id
	@Column(name = "id_")
	private Long id;

	@Column(name = "code_", nullable = false, length = 16)
	private String code;

	@Column(name = "name_", nullable = false)
	private String name;

	@Column(name = "address_", nullable = false)
	private String address;

	@Column(name = "time_zone_", nullable = false)
	private String timeZone;

	@Enumerated(EnumType.STRING)
	@Column(name = "status_", nullable = false, length = 16)
	private Status status;

	@Column(name = "created_at_", nullable = false)
	private Instant createdAt;

	@Formula("st_x(location_)")
	private double lng;

	@Formula("st_y(location_)")
	private double lat;

	protected Lockermat() {
	}

	public double getLng() {
		return lng;
	}

	public double getLat() {
		return lat;
	}

	public enum Status {
		ACTIVE, SUSPENDED, DECOMMISSIONED
	}
}
