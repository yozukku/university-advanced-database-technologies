package pl.edu.pk.ztb.bagazomat.audit;

import com.fasterxml.jackson.annotation.JsonProperty;

/** @author Anton Gorokh */
public record AuditChange(@JsonProperty("f") String field, @JsonProperty("old") String oldValue, @JsonProperty("new") String newValue) {
}
