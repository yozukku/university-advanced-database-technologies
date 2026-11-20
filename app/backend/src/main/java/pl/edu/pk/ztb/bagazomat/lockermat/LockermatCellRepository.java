package pl.edu.pk.ztb.bagazomat.lockermat;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.NativeQuery;

import java.time.Instant;
import java.util.Optional;

/** @author Anton Gorokh */
public interface LockermatCellRepository extends JpaRepository<LockermatCell, Long> {

	@NativeQuery("""
			select c.id_
			from lockermat_cell_ c
			         join lockermat_ l on l.id_ = c.lockermat_id_
			where l.id_ = :lockermatId and l.status_ = 'ACTIVE'
			  and c.size_ = :size and c.status_ = 'IN_SERVICE'
			  and not exists (select 1 from reservation_ r
			                  where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
			                    and tstzrange(r.from_, r.to_, '[)') && tstzrange(cast(:from as timestamptz), cast(:to as timestamptz), '[)'))
			  and not exists (select 1 from reservation_ r
			                  where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= current_timestamp)
			order by c.number_
			limit 1
			for update of c skip locked
			""")
	Optional<Long> findFreeCell(long lockermatId, String size, Instant from, Instant to);
}
