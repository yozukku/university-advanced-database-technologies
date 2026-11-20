package pl.edu.pk.ztb.bagazomat.lockermat;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import org.hibernate.annotations.Formula;

import java.time.Instant;

/** @author Anton Gorokh */
@Entity
@Table(name = "lockermat_")
public class Lockermat {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "lockermat_id")
	@SequenceGenerator(name = "lockermat_id", sequenceName = "lockermat_id_seq_", allocationSize = 1)
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

	@Column(name = "status_", nullable = false, length = 16)
	private String status;

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
}
