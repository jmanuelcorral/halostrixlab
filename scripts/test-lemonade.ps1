<#
.SYNOPSIS
Tests model discovery and one chat request against an explicitly selected Lemonade API.
.DESCRIPTION
GET /models is read-only. POST /chat/completions performs inference and can load
the selected model or evict another model. Review GPU ownership before running.
No endpoint or model is selected by default; no credentials are requested.
.PARAMETER BaseUrl
Absolute HTTP or HTTPS API base URL, including /v1 when required.
Credentials, query strings, and fragments are not accepted.
.PARAMETER Model
Exact model ID returned by the selected endpoint's /models response.
.EXAMPLE
.\scripts\test-lemonade.ps1 -BaseUrl 'http://localhost:13305/v1' -Model 'YOUR_MODEL_ID'
.NOTES
Requires Windows PowerShell 5.1 or PowerShell 7 and System.Net.Http.
Uses no proxy. Discovery timeout: 15 seconds. Chat timeout: 90 seconds.
A nonempty content or reasoning_content response is sufficient for PASS;
the script does not require the model to return the literal LAN_OK token.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [ValidateScript({
        $uri = $null
        if ($_ -match '\s' -or
            -not [Uri]::TryCreate($_, [UriKind]::Absolute, [ref]$uri) -or
            $uri.Scheme -notin @('http', 'https') -or
            [string]::IsNullOrWhiteSpace($uri.Host) -or
            $uri.HostNameType -eq [UriHostNameType]::Unknown -or
            $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
            throw 'BaseUrl must be an absolute HTTP(S) URL with a valid host and no credentials, whitespace, query, or fragment.'
        }
        $true
    })]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Model
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($null -eq ('System.Net.Http.HttpClient' -as [type])) {
    Add-Type -AssemblyName System.Net.Http
}

function Invoke-LemonadeRequest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [ValidateSet('GET', 'POST')]
        [string]$Method = 'GET',

        [string]$Body,

        [int]$TimeoutSeconds = 15
    )

    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $client = New-Object System.Net.Http.HttpClient -ArgumentList $handler
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    $response = $null
    $content = $null

    try {
        if ($Method -eq 'POST') {
            $content = New-Object System.Net.Http.StringContent -ArgumentList @(
                $Body,
                [System.Text.Encoding]::UTF8,
                'application/json'
            )
            $response = $client.PostAsync($Uri, $content).GetAwaiter().GetResult()
        }
        else {
            $response = $client.GetAsync($Uri).GetAwaiter().GetResult()
        }

        if (-not $response.IsSuccessStatusCode) {
            throw "HTTP $([int]$response.StatusCode) ($($response.ReasonPhrase)) at $Uri."
        }

        return $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    }
    finally {
        if ($null -ne $response) {
            $response.Dispose()
        }
        if ($null -ne $content) {
            $content.Dispose()
        }
        $client.Dispose()
        $handler.Dispose()
    }
}

try {
    $base = $BaseUrl.TrimEnd('/')
    $modelsEndpoint = "$base/models"
    $chatEndpoint = "$base/chat/completions"

    $models = Invoke-LemonadeRequest -Uri $modelsEndpoint | ConvertFrom-Json
    if ($null -eq $models.data) {
        throw "The response from $modelsEndpoint does not contain 'data'."
    }

    $availableModel = @($models.data | Where-Object { $_.id -eq $Model })
    if ($availableModel.Count -ne 1) {
        throw "The requested model '$Model' must appear exactly once in $modelsEndpoint."
    }

    $payload = @{
        model       = $Model
        messages    = @(
            @{
                role    = 'user'
                content = 'Reply only with LAN_OK.'
            }
        )
        temperature = 0
        max_tokens  = 16
        stream      = $false
    } | ConvertTo-Json -Depth 4 -Compress

    $chat = Invoke-LemonadeRequest -Uri $chatEndpoint -Method POST -Body $payload -TimeoutSeconds 90 | ConvertFrom-Json
    if ($null -eq $chat.choices -or @($chat.choices).Count -lt 1 -or $null -eq $chat.choices[0].message) {
        throw "The response from $chatEndpoint does not contain a valid chat choice."
    }

    $message = $chat.choices[0].message
    $answer = [string]$message.content
    if ([string]::IsNullOrWhiteSpace($answer)) {
        $answer = [string]$message.reasoning_content
    }
    if ([string]::IsNullOrWhiteSpace($answer)) {
        throw "The response from $chatEndpoint contains neither content nor reasoning."
    }

    Write-Host 'Lemonade LAN test: PASS'
    Write-Host "Endpoint: $base"
    Write-Host "Model: $Model"
    Write-Host "Response: $($answer.Trim())"
    exit 0
}
catch {
    Write-Error "Lemonade LAN test: FAIL. $($_.Exception.Message)"
    exit 1
}
