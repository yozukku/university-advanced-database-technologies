package pl.edu.pk.ztb.bagazomat.lockermat;

import org.springframework.stereotype.Service;
import pl.edu.pk.ztb.bagazomat.api.InvalidRequestException;
import pl.edu.pk.ztb.bagazomat.lockermat.LockermatAvailability.SizeAvailability;
import pl.edu.pk.ztb.bagazomat.lockermat.LockermatRepository.AvailabilityRow;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.stream.Collectors;

/** @author Anton Gorokh */
@Service
class LockermatService {

	private final LockermatRepository lockermatRepository;

	LockermatService(LockermatRepository lockermatRepository) {
		this.lockermatRepository = lockermatRepository;
	}

	List<LockermatAvailability> findAvailable(String query, Instant from, Instant to) {
		if (!from.isBefore(to)) {
			throw new InvalidRequestException();
		}
		List<AvailabilityRow> rows = lockermatRepository.findAvailability(toPattern(query), from, to);
		return groupByLockermat(rows);
	}

	private String toPattern(String query) {
		String literal = query.strip()
				.replace("\\", "\\\\")
				.replace("%", "\\%")
				.replace("_", "\\_");
		return "%" + literal + "%";
	}

	private List<LockermatAvailability> groupByLockermat(List<AvailabilityRow> rows) {
		return rows.stream()
				.collect(Collectors.groupingBy(AvailabilityRow::getId, LinkedHashMap::new, Collectors.toList()))
				.values()
				.stream()
				.map(this::toLockermatAvailability)
				.toList();
	}

	private LockermatAvailability toLockermatAvailability(List<AvailabilityRow> sizeRows) {
		AvailabilityRow lockermat = sizeRows.getFirst();
		List<SizeAvailability> sizes = sizeRows.stream()
				.map(row -> new SizeAvailability(row.getSize(), row.getFree(), row.getPrice()))
				.toList();
		return new LockermatAvailability(lockermat.getId(), lockermat.getName(), lockermat.getAddress(), lockermat.getLng(), lockermat.getLat(), sizes);
	}
}
