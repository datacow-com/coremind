# Test Samples Directory

This directory contains test data for Phase 1 integration tests.

## Text Samples

The following text samples are provided for testing:

1. `sample_tech.txt` - Technology domain text
2. `sample_science.txt` - Science domain text
3. `sample_business.txt` - Business domain text
4. `sample_literature.txt` - Literature domain text
5. `sample_chinese.txt` - Chinese language text

## Image Samples

For VLM testing, we use publicly available images from Wikipedia Commons:

1. Ant image: https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Camponotus_flavomarginatus_ant.jpg/320px-Camponotus_flavomarginatus_ant.jpg
2. Cat image: https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Felis_silvestris_catus_lying_on_rice_straw.jpg/320px-Felis_silvestris_catus_lying_on_rice_straw.jpg
3. Landscape: https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/24701-nature-702.jpg/320px-24701-nature-702.jpg
4. Architecture: https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Tour_Eiffel_Wikimedia_Commons.jpg/240px-Tour_Eiffel_Wikimedia_Commons.jpg
5. Food: https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Good_Food_Display_-_NCI_Visuals_Online.jpg/320px-Good_Food_Display_-_NCI_Visuals_Online.jpg

## Usage

These samples are used by:

- `tests/integration/test_provider_real_api.py` - Real API integration tests
- `tests/integration/test_phase1_e2e.py` - E2E tests

## Notes

- Text samples are UTF-8 encoded
- Image URLs are from Wikipedia Commons (CC licensed)
- For local image testing, download images to this directory
