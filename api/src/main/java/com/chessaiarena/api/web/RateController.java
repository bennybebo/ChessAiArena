package com.chessaiarena.api.web;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.chessaiarena.api.dto.RateRequest;
import com.chessaiarena.api.service.RateClient;
import com.fasterxml.jackson.databind.JsonNode;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api")
public class RateController {

  private final RateClient rateClient;

  public RateController(RateClient rateClient) {
    this.rateClient = rateClient;
  }

  @PostMapping("/rate")
  public ResponseEntity<?> rate(@Valid @RequestBody RateRequest req) {
    boolean hasText = req.pgnText() != null && !req.pgnText().isBlank();
    boolean hasUrl  = req.pgnUrl()  != null && !req.pgnUrl().isBlank();
    if (!hasText && !hasUrl) {
      return ResponseEntity.badRequest().body(
        java.util.Map.of("error", "Provide pgnText or pgnUrl")
      );
    }
    JsonNode result = rateClient.rate(req);
    return ResponseEntity.ok(result);
  }
}
