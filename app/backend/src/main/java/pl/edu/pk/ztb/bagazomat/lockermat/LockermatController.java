package pl.edu.pk.ztb.bagazomat.lockermat;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.List;

/** @author Anton Gorokh */
@RestController
class LockermatController {

	private final LockermatService lockermatService;

	LockermatController(LockermatService lockermatService) {
		this.lockermatService = lockermatService;
	}

	@GetMapping("/api/lockermats")
	public List<LockermatAvailability> find(@RequestParam(defaultValue = "") String q, @RequestParam Instant from, @RequestParam Instant to) {
		return lockermatService.findAvailable(q, from, to);
	}
}
