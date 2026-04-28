Test keys generated for the KLM project

Files:
- aes-128-cbc.key.b64 : 16-byte AES key, Base64 encoded, suitable for variant AES-128-CBC
- aes-192-cbc.key.b64 : 24-byte AES key, Base64 encoded, suitable for variant AES-192-CBC
- aes-256-cbc.key.b64 : 32-byte AES key, Base64 encoded, suitable for variant AES-256-CBC
- aes-256-ctr.key.b64 : 32-byte AES key, Base64 encoded, suitable for variant AES-256-CTR
- aes-256-gcm.key.b64 : 32-byte AES key, Base64 encoded, suitable for variant AES-256-GCM (cryptography backend)
- rsa-2048-private.pem : RSA private key in PEM format
- rsa-2048-public.pem : RSA public key in PEM format

How to use AES files in the UI:
1. Open the .b64 file and copy its full content.
2. In the app, use Import cheie....
3. Choose the matching algorithm variant.
4. Paste the Base64 content into the encrypted_material field.

Notes:
- The UI expects Base64 text and then encrypts the key material before storing it in the DB.
- AES-GCM should be tested with backend auto or cryptography.
- master.key is separate and should not be used as an imported test key.
