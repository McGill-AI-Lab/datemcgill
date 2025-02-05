from sklearn.cluster import KMeans
import numpy as np
from sklearn.metrics import silhouette_score, calinski_harabasz_score
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
from typing import Dict, Tuple
import seaborn as sns
from sklearn.model_selection import train_test_split
from pinecone import Pinecone
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import logging
from src.ml.clustering.cluster_users import analyze_clusters

# Set up logging
def setup_logging():
    output_dir = 'outputs'
    os.makedirs(output_dir, exist_ok=True)

    # Create log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = os.path.join(output_dir, f'clustering_evaluation_{timestamp}.log')

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()  # This will also print to console
        ]
    )
    return log_filename

def find_optimal_k(results: Dict) -> int:
    """
    Find optimal k using Calinski-Harabasz score and elbow method
    """
    # Using Calinski-Harabasz score (higher is better)
    calinski_scores = results['calinski_scores']
    optimal_k_calinski = results['k_values'][np.argmax(calinski_scores)]

    # Using elbow method
    inertias = results['inertias']
    k_values = results['k_values']

    # Calculate the elbow point using the maximum curvature method
    # Calculate the angle of the curve at each point
    angles = []
    for i in range(1, len(k_values)-1):
        point1 = np.array([k_values[i-1], inertias[i-1]])
        point2 = np.array([k_values[i], inertias[i]])
        point3 = np.array([k_values[i+1], inertias[i+1]])

        # Vectors from point2 to point1 and point3
        vector1 = point1 - point2
        vector2 = point3 - point2

        # Normalize vectors
        vector1_normalized = vector1 / np.linalg.norm(vector1)
        vector2_normalized = vector2 / np.linalg.norm(vector2)

        # Calculate angle
        angle = np.arccos(np.clip(np.dot(vector1_normalized, vector2_normalized), -1.0, 1.0))
        angles.append(angle)

    optimal_k_elbow = k_values[np.argmax(angles) + 1]

    # Log the findings
    logging.info(f"Optimal k based on Calinski-Harabasz score: {optimal_k_calinski}")
    logging.info(f"Optimal k based on elbow method: {optimal_k_elbow}")

    # Use Calinski-Harabasz score as the primary metric
    return optimal_k_calinski

def save_results_json(results: Dict, stats: Dict):
    """Save evaluation results to JSON file"""
    output_dir = 'outputs'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(output_dir, f'clustering_results_{timestamp}.json')

    # Prepare results for JSON serialization
    json_results = {
            'evaluation_metrics': {
                'k_values': results['k_values'],
                'inertias': [float(x) for x in results['inertias']],
                'silhouette_scores': [float(x) for x in results['silhouette_scores']],
                'calinski_scores': [float(x) for x in results['calinski_scores']]
            },
            'cluster_statistics': {
                str(k): {
                    'size': int(v['size']),
                    'percentage': float(v['percentage']),
                    'mean_distance': float(v['mean_distance']),  # Updated key name
                    'density': float(v['density'])
                } for k, v in stats.items()
            },
            'timestamp': datetime.now().isoformat(),
    }

    with open(output_file, 'w') as f:
        json.dump(json_results, f, indent=4)

    return output_file

def evaluate_kmeans(embeddings: np.ndarray, k_range: range = range(4, 21)) -> Dict:
    """
    Evaluate KMeans clustering for different values of k.
    """
    results = {
        'k_values': list(k_range),
        'inertias': [],
        'silhouette_scores': [],
        'calinski_scores': []
    }

    logging.info(f"Starting KMeans evaluation for k range: {min(k_range)} to {max(k_range)}")

    for k in k_range:
        logging.info(f"Evaluating k={k}")
        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        labels = kmeans.fit_predict(embeddings)

        inertia = kmeans.inertia_
        silhouette = silhouette_score(embeddings, labels)
        calinski = calinski_harabasz_score(embeddings, labels)

        results['inertias'].append(inertia)
        results['silhouette_scores'].append(silhouette)
        results['calinski_scores'].append(calinski)

        logging.info(f"k={k}: Inertia={inertia:.2f}, Silhouette={silhouette:.3f}, Calinski-Harabasz={calinski:.2f}")

    return results

def visualize_evaluation(results: Dict) -> None:
    """Plot evaluation metrics."""
    output_dir = 'outputs'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # elbow curve
    axes[0].plot(results['k_values'], results['inertias'], 'bo-')
    axes[0].set_xlabel('Number of clusters (k)')
    axes[0].set_ylabel('Inertia')
    axes[0].set_title('Elbow Method')

    # silhouette scores
    axes[1].plot(results['k_values'], results['silhouette_scores'], 'ro-')
    axes[1].set_xlabel('Number of clusters (k)')
    axes[1].set_ylabel('Silhouette Score')
    axes[1].set_title('Silhouette Analysis')

    # Calinski-Harabasz scores
    axes[2].plot(results['k_values'], results['calinski_scores'], 'go-')
    axes[2].set_xlabel('Number of clusters (k)')
    axes[2].set_ylabel('Calinski-Harabasz Score')
    axes[2].set_title('Calinski-Harabasz Index')

    plt.tight_layout()
    output_file = os.path.join(output_dir, f'kmeans_evaluation_{timestamp}.png')
    plt.savefig(output_file)
    plt.close()

    logging.info(f"Saved evaluation plots to {output_file}")

def main():
    # Setup logging
    log_file = setup_logging()
    logging.info("Starting clustering evaluation")

    # Load data from Pinecone
    load_dotenv(dotenv_path='.env')
    pc = Pinecone(api_key=os.getenv("PINECONE_KEY"))
    index = pc.Index(host="https://matching-index-goovj0m.svc.aped-4627-b74a.pinecone.io")

    logging.info("Querying Pinecone for embeddings")
    all_bio_records = index.query(
        vector=[float(0)] * 384,
        namespace='bio-embeddings',
        filter={},
        top_k=1000,
        include_values=True
    )

    # Convert to numpy array
    embeddings = np.array([match['values'] for match in all_bio_records['matches']])
    logging.info(f"Retrieved embeddings shape: {embeddings.shape}")

    # Normalize embeddings
    scaler = StandardScaler()
    embeddings_normalized = scaler.fit_transform(embeddings)
    logging.info("Normalized embeddings")

    # evaluate different k values
    logging.info("Evaluating different numbers of clusters...")
    results = evaluate_kmeans(embeddings_normalized)
    visualize_evaluation(results)

    # COMMENTED OUT BCZ SILHOUETTE SCORE IS TOO VOLATILE
    # Find optimal k using silhouette score
    #optimal_k = results['k_values'][np.argmax(results['silhouette_scores'])]
    #logging.info(f"Optimal number of clusters based on silhouette score: {optimal_k}")

    # USE FIND OPTIMAL (BASED ON CALINSKI INSTEAD)
    # Find optimal k using the new method
    optimal_k = find_optimal_k(results)
    logging.info(f"Selected optimal number of clusters: {optimal_k}")

    # Final clustering with optimal k
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init='auto')
    kmeans.fit(embeddings_normalized)

    # Get labels and centroids
    all_labels = kmeans.labels_
    centroids = kmeans.cluster_centers_  # Get the centroids array

    # Now pass the correct arguments to analyze_clusters
    cluster_stats = analyze_clusters(all_labels, centroids, embeddings_normalized)

    # Save results to JSON
    json_file = save_results_json(results, cluster_stats)
    logging.info(f"Saved detailed results to {json_file}")

    # Log cluster statistics
    logging.info("\nCluster Analysis:")
    for cluster_id, stats in cluster_stats.items():
        logging.info(f"\n{cluster_id}:")
        logging.info(f"Size: {stats['size']} ({stats['percentage']:.1f}%)")
        logging.info(f"Mean distance: {stats['mean_distance']:.3f}")
        logging.info(f"Density: {stats['density']:.3f}")

    logging.info("Evaluation complete")

if __name__ == "__main__":
    main()
