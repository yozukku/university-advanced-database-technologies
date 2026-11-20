package pl.edu.pk.ztb.bagazomat.access;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** @author Anton Gorokh */
@RestController
class AccessCodeController {

	private final AccessCodeService accessCodeService;

	AccessCodeController(AccessCodeService accessCodeService) {
		this.accessCodeService = accessCodeService;
	}

	@GetMapping("/api/orders/{id}/codes")
	public List<AccessCodeView> findActive(@AuthenticationPrincipal Jwt jwt, @PathVariable long id) {
		return accessCodeService.findActiveCodes(jwt, id);
	}
}
