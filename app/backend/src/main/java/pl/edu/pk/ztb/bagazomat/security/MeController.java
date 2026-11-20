package pl.edu.pk.ztb.bagazomat.security;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** @author Anton Gorokh */
@RestController
class MeController {

	@GetMapping("/api/me")
	public Profile me(@AuthenticationPrincipal Jwt jwt) {
		return new Profile(jwt.getSubject(), jwt.getClaimAsString("name"), jwt.getClaimAsString("email"));
	}

	record Profile(String sub, String name, String email) {
	}
}
