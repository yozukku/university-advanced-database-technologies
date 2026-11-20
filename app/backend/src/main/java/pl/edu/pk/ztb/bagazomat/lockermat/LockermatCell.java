package pl.edu.pk.ztb.bagazomat.lockermat;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

/** @author Anton Gorokh */
@Entity
@Immutable
@Table(name = "lockermat_cell_")
public class LockermatCell {

	@Id
	@Column(name = "id_")
	private Long id;

	@Column(name = "lockermat_id_", nullable = false)
	private Long lockermatId;

	@Column(name = "number_", nullable = false)
	private Short number;

	@Enumerated(EnumType.STRING)
	@Column(name = "size_", nullable = false, length = 10)
	private CellSize size;

	@Enumerated(EnumType.STRING)
	@Column(name = "status_", nullable = false, length = 16)
	private Status status;

	protected LockermatCell() {
	}

	public enum Status {
		IN_SERVICE, OUT_OF_SERVICE
	}
}
