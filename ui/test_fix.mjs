import { match_str } from './app/utils/ytdlp'

const testData = {
  "age_limit": 0,
  "comment_count": 6,
  "channel_id": "UC-7oMv6E4Uz2tF51w5Sj49w",
  "uploader_url": "https://www.youtube.com/@PlayFramePlus"
}

// The filter that was incorrectly matching before
const filter = "channel_id = 'UCfmrcEdes7yDtEISGPM1T-A' & availability = subscriber_only"

console.log('Test data:', testData)
console.log('Filter:', filter)
console.log('Result:', match_str(filter, testData))
console.log('Expected: false')

// Test individual parts
console.log('\nTesting parts individually:')
console.log('Part 1 (channel_id = \'UCfmrcEdes7yDtEISGPM1T-A\'):', match_str("channel_id = 'UCfmrcEdes7yDtEISGPM1T-A'", testData))
console.log('Part 2 (availability = subscriber_only):', match_str("availability = subscriber_only", testData))

// Test correct channel_id
console.log('\nTesting with correct channel_id:')
console.log('Correct channel_id:', match_str("channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w'", testData))
