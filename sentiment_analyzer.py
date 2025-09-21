import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import pickle
import os
from textblob import TextBlob
import re

class SentimentAnalyzer:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=10000, stop_words='english')
        self.model = LogisticRegression(random_state=42)
        self.is_trained = False
        self.model_path = 'sentiment_model.pkl'
        self.vectorizer_path = 'sentiment_vectorizer.pkl'
        
    def preprocess_text(self, text):
        """Preprocess text for sentiment analysis"""
        if not isinstance(text, str):
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        
        # Remove user mentions and hashtags
        text = re.sub(r'@\w+|#\w+', '', text)
        
        # Remove special characters and digits
        text = re.sub(r'[^a-zA-Z\s]', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def create_synthetic_sentiment140_data(self):
        """Create synthetic data similar to Sentiment140 for training"""
        # This is a simplified version - in production, you'd use the actual Sentiment140 dataset
        positive_samples = [
            "I love this event! It's amazing and wonderful.",
            "Great experience, highly recommend to everyone.",
            "Fantastic presentation, learned so much today.",
            "Excellent organization and great speakers.",
            "Outstanding event, will definitely attend again.",
            "Perfect venue and amazing content.",
            "Wonderful experience, thank you so much!",
            "Brilliant ideas and great networking opportunities.",
            "Superb quality and very informative.",
            "Outstanding performance and great atmosphere.",
            "Excellent service and friendly staff.",
            "Amazing event with great speakers.",
            "Fantastic experience, highly recommended.",
            "Wonderful time, learned a lot.",
            "Great event with excellent content.",
            "Perfect organization and great venue.",
            "Outstanding presentation and valuable insights.",
            "Excellent networking opportunities.",
            "Amazing atmosphere and great people.",
            "Fantastic speakers and engaging content.",
            "Delighted with the sessions; truly inspiring and uplifting.",
            "Thrilled by the insightful talks and stellar delivery.",
            "Stellar experience from start to finish; absolutely superb.",
            "Marvelous workshop with clear, actionable takeaways.",
            "Top‑notch speakers and a vibrant, energizing crowd.",
            "Exceptional curation and flawlessly executed agenda.",
            "Phenomenal content depth and remarkably engaging format.",
            "Impressed by the seamless logistics and warm hospitality.",
            "A standout conference—memorable, enriching, and motivating.",
            "Super uplifting vibe and remarkably helpful staff.",
            "Gold‑standard event quality; exceeded expectations.",
            "Terrific panels with illuminating perspectives.",
            "Couldn’t be happier with the insights I gained.",
            "A joyous, rewarding experience—truly worthwhile."
        ]
        
        # Add explicit samples containing the literal word "positive"
        positive_samples.extend([
            "This session was positive and uplifting.",
            "Very positive experience overall.",
            "I feel positive about the outcomes.",
            "Positive energy throughout and positive results."
        ])

        # Add more variety to positive samples
        positive_samples.extend([
            "Incredibly inspiring talks with actionable insights.",
            "Empowering discussions that left me motivated and confident.",
            "A delightful program—thoughtful, engaging, and rewarding.",
            "Exceptional clarity from speakers; content was enlightening.",
            "Seamless execution and an uplifting community vibe.",
            "Captivating sessions with brilliant storytelling.",
            "A transformative experience—truly eye‑opening and energizing.",
            "Super informative and genuinely enjoyable throughout.",
            "Encouraging atmosphere and remarkably supportive staff.",
            "Outstanding facilitation and top‑tier content curation.",
            "Highly commendable effort; exceeded my expectations.",
            "Insightful case studies with practical, positive outcomes.",
            "Remarkably smooth logistics and a welcoming tone.",
            "Brimming with positivity—great energy and collaboration.",
            "A stellar lineup and exceptionally engaging panels.",
            "Refreshing perspectives and constructive, optimistic dialogue.",
            "Bright, cheerful environment that boosted my morale.",
            "A superb blend of depth, clarity, and enthusiasm.",
            "Grateful for the constructive feedback and positive reinforcement.",
            "Heartening stories that inspired confidence and optimism."
        ])

        # Teach model the token "awesome" with varied contexts
        positive_samples.extend([
            "Awesome event with fantastic speakers!",
            "Totally awesome experience from start to finish.",
            "The workshops were awesome and super helpful.",
            "Awesome vibe, awesome people, awesome content.",
            "Such an awesome lineup—truly impressive.",
            "Awesome insights delivered with clarity.",
            "Had an awesome time learning and connecting.",
            "The venue was awesome and the sessions were stellar.",
            "Awesome delivery and remarkable takeaways.",
            "Simply awesome—well organized and inspiring."
        ])
        
        negative_samples = [
            "Terrible event, waste of time and money.",
            "Poor organization and boring speakers.",
            "Disappointing experience, would not recommend.",
            "Bad venue and unprofessional staff.",
            "Awful presentation, learned nothing useful.",
            "Worst event I've ever attended.",
            "Terrible quality and poor service.",
            "Disappointing content and bad atmosphere.",
            "Horrible experience, complete waste of time.",
            "Poor speakers and unorganized event.",
            "Bad venue and terrible food.",
            "Disappointing and unprofessional.",
            "Worst networking event ever.",
            "Terrible speakers and boring content.",
            "Awful organization and poor quality.",
            "Disappointing experience overall.",
            "Bad event with no value.",
            "Terrible atmosphere and poor service.",
            "Worst conference I've attended.",
            "Disappointing and not worth the time.",
            "Abysmal planning and chaotic scheduling throughout.",
            "Dreadful sound quality and a painfully dull agenda.",
            "Lousy logistics; everything felt sloppy and rushed.",
            "Subpar speakers with incoherent, meandering talks.",
            "Shoddy execution and constant delays ruined the flow.",
            "A letdown—uninspired content and negligible value.",
            "Clumsy coordination and bafflingly poor time management.",
            "Disastrous check‑in; lines were endless and frustrating.",
            "Miserable experience with rude, unhelpful staff.",
            "Utterly forgettable—bland topics and zero engagement.",
            "Inadequate facilities and cramped seating throughout.",
            "Painfully underwhelming; I left early.",
            "Second‑rate production with frequent technical glitches.",
            "Regrettable attendance—did not meet basic expectations."
        ]
        
        neutral_samples = [
            "The event was okay, nothing special.",
            "Average presentation with standard content.",
            "Decent event, met some interesting people.",
            "Standard conference with typical speakers.",
            "Okay experience, learned a few things.",
            "Average quality, nothing remarkable.",
            "Decent organization and standard content.",
            "Okay event, nothing to complain about.",
            "Standard presentation with normal quality.",
            "Decent networking opportunities.",
            "Average speakers and typical content.",
            "Okay venue and standard service.",
            "Decent experience overall.",
            "Average event with normal quality.",
            "Standard conference, nothing special.",
            "Okay presentation and decent content.",
            "Average organization and typical speakers.",
            "Decent networking and standard quality.",
            "Okay experience, nothing remarkable.",
            "Standard event with normal atmosphere.",
            "Mediocre overall; parts were fine, others ordinary.",
            "Neither great nor bad—just acceptable.",
            "Run‑of‑the‑mill topics with predictable insights.",
            "Nothing stood out; it was serviceable.",
            "Balanced mix of talks; outcome was fair.",
            "It met expectations without exceeding them.",
            "Routine agenda and a steady pace.",
            "Adequate sessions with passable delivery.",
            "Fine for a typical workday seminar.",
            "Mixed quality but generally tolerable.",
            "Plain format; content was straightforward.",
            "Ordinary venue with standard amenities.",
            "Satisfactory logistics and predictable schedule.",
            "Neutral takeaways; nothing memorable."
        ]
        
        # Ensure no duplicate entries while preserving order
        positive_samples = list(dict.fromkeys(positive_samples))
        negative_samples = list(dict.fromkeys(negative_samples))
        neutral_samples = list(dict.fromkeys(neutral_samples))
        
        # Create DataFrame
        data = []
        for text in positive_samples:
            data.append({'text': text, 'sentiment': 1})  # 1 for positive
        for text in negative_samples:
            data.append({'text': text, 'sentiment': 0})  # 0 for negative
        for text in neutral_samples:
            data.append({'text': text, 'sentiment': 2})  # 2 for neutral
            
        return pd.DataFrame(data)
    
    def train_model(self):
        """Train the sentiment analysis model"""
        print("Creating training data...")
        df = self.create_synthetic_sentiment140_data()
        
        # Preprocess text
        df['processed_text'] = df['text'].apply(self.preprocess_text)
        
        # Remove empty texts
        df = df[df['processed_text'].str.len() > 0]
        
        # Split data
        X = df['processed_text']
        y = df['sentiment']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Vectorize text
        print("Vectorizing text...")
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_test_vec = self.vectorizer.transform(X_test)
        
        # Train model
        print("Training model...")
        self.model.fit(X_train_vec, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_vec)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Model accuracy: {accuracy:.2f}")
        
        self.is_trained = True
        
        # Save model
        self.save_model()
        
        return accuracy
    
    def load_model(self):
        """Load pre-trained model"""
        if os.path.exists(self.model_path) and os.path.exists(self.vectorizer_path):
            try:
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.vectorizer_path, 'rb') as f:
                    self.vectorizer = pickle.load(f)
                self.is_trained = True
                print("Model loaded successfully")
                return True
            except Exception as e:
                print(f"Error loading model: {e}")
                return False
        return False
    
    def save_model(self):
        """Save trained model"""
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.vectorizer_path, 'wb') as f:
                pickle.dump(self.vectorizer, f)
            print("Model saved successfully")
        except Exception as e:
            print(f"Error saving model: {e}")
    
    def predict_sentiment(self, text):
        """Predict sentiment of given text"""
        if not self.is_trained:
            if not self.load_model():
                print("Training new model...")
                self.train_model()
        
        # Preprocess text
        processed_text = self.preprocess_text(text)
        
        if not processed_text:
            return {'sentiment': 'neutral', 'confidence': 0.5, 'score': 0}
        
        # Vectorize
        text_vec = self.vectorizer.transform([processed_text])
        
        # Handle out-of-vocabulary single-word or rare inputs that produce zero features
        if hasattr(text_vec, 'nnz') and text_vec.nnz == 0:
            return {'sentiment': 'neutral', 'confidence': 0.5, 'score': 0}
        
        # Predict
        prediction = self.model.predict(text_vec)[0]
        confidence = np.max(self.model.predict_proba(text_vec))
        
        # Map prediction to sentiment
        sentiment_map = {0: 'negative', 1: 'positive', 2: 'neutral'}
        sentiment = sentiment_map.get(prediction, 'neutral')
        
        # Calculate sentiment score (-1 to 1)
        if sentiment == 'positive':
            score = confidence
        elif sentiment == 'negative':
            score = -confidence
        else:
            score = 0
        
        return {
            'sentiment': sentiment,
            'confidence': float(confidence),
            'score': float(score)
        }
    
    def analyze_batch(self, texts):
        """Analyze sentiment for multiple texts"""
        results = []
        for text in texts:
            result = self.predict_sentiment(text)
            results.append(result)
        return results
    
    def get_sentiment_stats(self, texts):
        """Get sentiment statistics for a collection of texts"""
        results = self.analyze_batch(texts)
        
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        total_score = 0
        total_confidence = 0
        
        for result in results:
            sentiment_counts[result['sentiment']] += 1
            total_score += result['score']
            total_confidence += result['confidence']
        
        total_texts = len(texts)
        avg_score = total_score / total_texts if total_texts > 0 else 0
        avg_confidence = total_confidence / total_texts if total_texts > 0 else 0
        
        return {
            'total_texts': total_texts,
            'sentiment_counts': sentiment_counts,
            'sentiment_percentages': {
                'positive': (sentiment_counts['positive'] / total_texts) * 100,
                'negative': (sentiment_counts['negative'] / total_texts) * 100,
                'neutral': (sentiment_counts['neutral'] / total_texts) * 100
            },
            'average_score': avg_score,
            'average_confidence': avg_confidence
        }

# Initialize global sentiment analyzer
sentiment_analyzer = SentimentAnalyzer()

# Train or load model on startup
if not sentiment_analyzer.load_model():
    print("Training new sentiment analysis model...")
    sentiment_analyzer.train_model()
