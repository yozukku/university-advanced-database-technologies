package pl.edu.pk.ztb.bagazomat.audit;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.security.oauth2.jwt.Jwt;

/** @author Anton Gorokh */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record AuditActor(Kind kind, @JsonProperty("keycloak_id") String keycloakId, String email, String phone, String job) {

	public static AuditActor customer(Jwt jwt) {
		return new AuditActor(Kind.CUSTOMER, jwt.getSubject(), jwt.getClaimAsString("email"), null, null);
	}

	public static AuditActor recipient(Jwt jwt, String phone) {
		return new AuditActor(Kind.RECIPIENT, jwt.getSubject(), jwt.getClaimAsString("email"), phone, null);
	}

	public static AuditActor system(String job) {
		return new AuditActor(Kind.SYSTEM, null, null, null, job);
	}

	public enum Kind {
		CUSTOMER, RECIPIENT, SYSTEM
	}
}
