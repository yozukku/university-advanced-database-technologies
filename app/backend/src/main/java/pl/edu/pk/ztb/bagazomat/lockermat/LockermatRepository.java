package pl.edu.pk.ztb.bagazomat.lockermat;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.NativeQuery;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/** @author Anton Gorokh */
public interface LockermatRepository extends JpaRepository<Lockermat, Long> {

	@NativeQuery("""
			select l.id_ as id, l.name_ as name, l.address_ as address, st_x(l.location_) as lng, st_y(l.location_) as lat, t.size_ as size,
			       t.storage_price_per_day_ * ceil(extract(epoch from (cast(:to as timestamptz) - cast(:from as timestamptz))) / 86400) as price,
			       (select count(*)
			        from lockermat_cell_ c
			        where c.lockermat_id_ = l.id_ and c.size_ = t.size_ and c.status_ = 'IN_SERVICE'
			          and not exists (select 1 from reservation_ r
			                          where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
			                            and tstzrange(r.from_, r.to_, '[)') && tstzrange(cast(:from as timestamptz), cast(:to as timestamptz), '[)'))
			          and not exists (select 1 from reservation_ r
			                          where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= current_timestamp)) as free
			from lockermat_ l
			         cross join tariff_ t
			where l.status_ = 'ACTIVE'
			  and tstzrange(t.valid_from_, t.valid_to_, '[)') @> now()
			  and (lower(l.address_) like lower(:pattern) or lower(l.name_) like lower(:pattern))
			order by l.address_, l.name_, l.id_, case t.size_ when 'S' then 1 when 'M' then 2 else 3 end
			""")
	List<AvailabilityRow> findAvailability(String pattern, Instant from, Instant to);

	interface AvailabilityRow {

		Long getId();

		String getName();

		String getAddress();

		Double getLng();

		Double getLat();

		CellSize getSize();

		Long getFree();

		BigDecimal getPrice();
	}
}
