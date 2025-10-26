xAI API rate limits are designed to manage the volume of requests and ensure reliable service. These limits vary depending on the specific Grok model being used and are typically expressed in terms of requests per minute (RPM) and tokens per minute (TPM).

Key aspects of xAI API rate limits:

- **Model-Specific Limits:** 

  Each Grok model, such as Grok-4-fast-non-reasoning or Grok-3-mini, has its own defined rate limits for RPM and TPM. For example, Grok-4-fast-non-reasoning has a rate limit of 4M TPM and 480 RPM, while Grok-3-mini has a limit of 480 RPM.

- **Error Handling:** 

  Exceeding these limits will result in an HTTP 429 "Too Many Requests" error.

- **Requesting Higher Limits:** 

  If higher usage is anticipated, users can request an increase in their rate limits by contacting xAI support.

- **Consumption Patterns:** 

  Users are encouraged to optimize their application's consumption patterns to stay within the allocated limits, potentially by implementing request throttling or incorporating retry logic.

- **API Key Management:** 

  Rate limits can be configured when creating API keys, allowing for granular control over individual key usage. For instance, specific limits on queries per second and queries per minute can be set.

- **Project-Level Management:** 

  Within an organization, rate limits can be managed at the project level, allowing for customized limits and usage monitoring for different teams or applications.

Example Rate Limits (as of July 2025):

| Model                     | Rate limits     |
| ------------------------- | --------------- |
| grok-4-fast-non-reasoning | 4M tpm, 480 rpm |
| grok-4-0709               | 2M tpm, 480 rpm |
| grok-3-mini               | 480 rpm         |
| grok-3                    | 600 rpm         |



More details:

The XAI API rate limits are tied to specific models and your subscription plan. Access to the API requires an X Premium subscription or a direct subscription through XAI. 

X Premium (Standard)

This subscription, priced at $8/month, offers basic API access with the following limits: 

- **Monthly requests:** 10,000
- **Requests per minute:** 100
- **Concurrent requests:** 2
- **Max tokens per request:** 4,096 

------

X Premium+ (Enhanced)

This subscription, priced at $16/month, significantly increases the API limits: 

- **Monthly requests:** 50,000
- **Requests per minute:** 500
- **Concurrent requests:** 10
- **Max tokens per request:** 8,192 

------

XAI direct subscriptions

For more advanced use cases, XAI offers direct subscriptions with specialized models and higher limits: 

| Model                       | RPM  | Tokens per minute (TPM) | Description                                 |
| :-------------------------- | :--- | :---------------------- | :------------------------------------------ |
| `grok-4-fast-reasoning`     | 480  | 4M                      | Optimized for speed with strong reasoning.  |
| `grok-4-fast-non-reasoning` | 480  | 4M                      | Optimized for speed on non-reasoning tasks. |
| `grok-4-0709`               | 480  | 2M                      | A powerful general-purpose model.           |
| `grok-3-mini`               | 480  | Not specified           | A lightweight model for quantitative tasks. |

Important considerations

- **Image input tokens:** For models that accept images, token consumption depends on image size, ranging from 256 to 1792 tokens per image.
- **Custom limits:** It is possible to set your own custom rate limits when creating an API key through the [XAI console](https://console.x.ai/).
- **Overages:** You can configure your billing preferences to allow for additional requests beyond your included monthly allowance, typically for a fee of $0.001 per request.
- **Excessive requests:** If you exceed your rate limits, the API will return an error. You may need to implement request throttling or retry logic in your application to handle these errors gracefully. 