package pl.edu.pk.ztb.bagazomat.opening;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

/** @author Anton Gorokh */
@RestController
class OpeningController {

	private final OpeningService openingService;

	OpeningController(OpeningService openingService) {
		this.openingService = openingService;
	}

	@PostMapping("/api/reservations/{id}/open")
	public OpeningView open(@AuthenticationPrincipal Jwt jwt, @PathVariable long id) {
		return openingService.open(jwt, id);
	}
}
