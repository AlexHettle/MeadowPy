# Word Counter
# Counts how often each word appears in text.

text = """
Python is a great programming language.
Python is easy to learn and fun to use.
Many people love Python because it is simple.
"""

# Clean up the text
# .lower() makes everything lowercase
# .split() breaks text into a list of words
words = text.lower().split()

# Remove punctuation from each word
clean_words = []
for word in words:
    # .strip() removes characters from the edges
    cleaned = word.strip('.,!?;:\'"')
    if cleaned:  # Skip empty strings
        clean_words.append(cleaned)

# Count each word using a dictionary
word_counts = {}
for word in clean_words:
    if word in word_counts:
        word_counts[word] += 1
    else:
        word_counts[word] = 1

# Sort by count (most common first)
# sorted() with key= tells Python how to sort
sorted_words = sorted(word_counts.items(),
                      key=lambda pair: pair[1],
                      reverse=True)

print(f"Total words: {len(clean_words)}")
print(f"Unique words: {len(word_counts)}")
print("\nWord frequencies:")
for word, count in sorted_words:
    bar = "#" * count  # Visual bar
    print(f"  {word:12} {count:2} {bar}")
