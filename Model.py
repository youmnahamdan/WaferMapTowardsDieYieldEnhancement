import sqlite3
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM
from math import sqrt, pow
import numpy as np
import io 
import matplotlib.pyplot as plt # For data visualization
import matplotlib
matplotlib.use('Agg') # Use Agg backend to prevent creation of plots as GUIs

class die_level_prediction:
    def __init__(self, db_name, mid, kernel='rbf', gamma='scale', nu=0.06):
        self.kernel = kernel
        self.gamma = gamma
        self.nu = nu
        self.mid = mid
        self.db_name = db_name
        self.die_data_df = None
        self.scaled_data_df = None
        self.model = None
        self.figures_list = []
        self.count_df = pd.DataFrame({
                'MasterID': [0],
                'die_count': [0],
                'good_die_count_before': [0],
                'bad_die_count_before':[0],
                'good_die_count_after': [0],
                'bad_die_count_after':[0]
            })
        self.connect_to_db()

    def connect_to_db(self):
        """
        Connect to the database
        """
        self._conn = sqlite3.connect(self.db_name)
        self._cursor = self.conn.cursor()

    def load_data_from_db(self):
            """
            Load data from the database using the provided query.
            """
            # Read die data from db as a dataframe 
            self.die_data_df = pd.read_sql('SELECT * FROM die_info WHERE MasterID = ?', self.conn, params=(self.mid,))
            
            # Fetch wafer center coordinates
            result = self.cursor.execute('SELECT CenterX, CenterY FROM wafer_config WHERE MasterID = ?',  (self.mid,))
            self.centers = result.fetchall()[0]
            
            # Fetch die dimensions from db
            result = self.cursor.execute('SELECT DieWidth, DieHeight FROM wafer_config WHERE MasterID = ?',  (self.mid,))
            self.die_dim = result.fetchall()[0]
        
            # Storing count values
            self.count_df['MasterID','die_count'] = self.mid,self.die_data_df['Passing'].count()
            self.count_df['bad_die_count_before']  = self.die_data_df[self.die_data_df['Passing'] == 0].count()
            self.count_df['good_die_count_before'] = self.die_data_df[self.die_data_df['Passing'] == 1].count()

    def calculate_effect_probability(self):
        """
        Calculate the effect probability weights for neighboring dies based on their
        distance from a reference die.

        Returns:
            List[float]: Weights for the corner, south-north, and left-right neighbors.
        """
        try:
            # Die dimensions
            x, y = self.die_dim
            
            if x <= 0 or y <= 0:
                raise ValueError("Die dimensions must be positive non-zero values.")
            
            # Calculate the total distance for normalization
            distance_corner = 4 / sqrt(pow(x, 2) + pow(y, 2))    # Distance from corners
            distance_lr = 2 / x          # Distance from left and right
            distance_sn = 2 / y          # Distance from south and north
            total_distance = distance_corner + distance_lr + distance_sn

            # Calculate weights for each neighbor type
            weight_corner = distance_corner / total_distance
            weight_lr = distance_lr / total_distance
            weight_sn = distance_sn / total_distance
            
            # Return weights
            return [weight_corner, weight_sn, weight_corner, weight_lr, weight_lr, weight_corner, weight_sn, weight_corner]

        except TypeError:
            raise ValueError("Die dimensions must be a tuple or list of two positive numbers.")
        except Exception as e:
            raise e

    def calculate_local_yield_8(self):
        """
        Calculate the local yield for each die based on its 8 neighbors and store the results
        in the dataframe.
        """
        # Add necessary columns to the dataframe
        self.die_data_df['Visited'] = False                # Track visited dies to avoid redundant processing  
        self.die_data_df['distance_from_center'] = 0.0     # Store the distance from center for each die
        self.die_data_df['edge'] = False                   # Flag edge dies
        self.die_data_df['local_yield'] = 0.0              # Store local region yield
        self.die_data_df['good_neighbor'] = 0              # Good neighbors count
        self.die_data_df['bad_neighbor'] = 0               # Bad neighbors count
        
        # Number of surrounding neighbors 
        ith_neighborhood = 8
        
        # Neighbors coordinates from reference die (mask)
        die_neighborhood = [(-1, 1), (0, 1), (1, 1), (-1, 0), (1, 0), (-1, -1), (0, -1), (1, -1)]
        
        # Weights
        effect_probability = self.calculate_effect_probability()

        for index, record in self.die_data_df.iterrows():
            if not record['Visited']:
                local_yield = 0
                good_neighbors = 0
                bad_neighbors = 0
                neighbors = 0
                die_coords = (record['DieX'], record['DieY'])

                for i in range(ith_neighborhood):
                    neighbor_coords = tuple(die_neighborhood[i][j] + die_coords[j] for j in range(2))
                    pass_fail = self.die_data_df.loc[
                        (self.die_data_df['DieX'] == neighbor_coords[0]) & 
                        (self.die_data_df['DieY'] == neighbor_coords[1]), 
                        'Passing'
                    ]

                    if not pass_fail.empty:
                        neighbors += 1
                        if pass_fail.values[0] == 1:  # Die passes parametric tests
                            good_neighbors += 1
                            local_yield += effect_probability[i]
                        else: 
                            bad_neighbors +=1
                
                # Update dataframe with calculated values
                self.die_data_df.at[index, 'Visited'] = True
                self.die_data_df.at[index, 'good_neighbor'] = good_neighbors
                self.die_data_df.at[index, 'distance_from_center'] = sqrt(
                    pow(die_coords[0] - self.centers[0], 2) + pow(die_coords[1] - self.centers[1], 2)
                )
                self.die_data_df.at[index, 'local_yield'] = local_yield
                self.die_data_df.at[index, 'edge'] = (neighbors < 8)
                self.die_data_df.at[index, 'bad_neighbor'] = bad_neighbors

    def train_ocsvm(self):
        """
        Train One-Class SVM model.
        """
        # Extract the features to train the model     
        self.features = self.die_data_df.loc[(self.die_data_df['edge'] == False) & (self.die_data_df.bad_neighbor.between(2,8)),['bad_neighbor','local_yield']]
        
        # Initialize and fit the One-Class SVM model
        self.model = OneClassSVM(kernel = self.kernel, gamma = self.gamma, nu = self.nu )
        self.model.fit(self.features)

    def predict(self):
        """
        Predict anomalies using the trained One-Class SVM model.
        
        Returns:
        predictions [numpy.ndarray] 
        outliers [DataFrame]
        """
        if self.model is None:
            raise ValueError("Model must be trained before making predictions.")

        # Predict using the trained model
        predictions = self.model.predict(self.features)
        
        # Find outliers
        outliers_index = np.where(predictions == -1)[0]
        outliers = self.features.iloc[outliers_index]
        
        # Number of outliers
        self.num_outliers = len(outliers)
        
        # Mark outliers as faulty
        self.die_data_df.loc[self.features.iloc[outliers_index].index, 'Passing'] = 0
        
        # Store count values
        count_pass = self.die_data_df['Passing'].value_counts()
        self.count_df['bad_die_count_after']  = count_pass[0]
        self.count_df['good_die_count_after'] = count_pass[1]
        
        return predictions, outliers
    
    def visualize(self):
        # 2D die_count to Local Yield visualization
        plt.figure()
        yield_die_count = self.die_data_df['local_yield'].value_counts()
        ax = yield_die_count.plot(kind='barh')
        ax.set_xlabel('Die Count')
        ax.set_ylabel('Local Yield')

        # Save the plot to an in-memory buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        self.figures_list.append(buf)


        # 2D die_count to HW Bin visualization
        plt.figure()
        HWB_die_count = self.die_data_df['HardwareBin'].value_counts()
        ax = HWB_die_count.plot(kind='barh')
        ax.set_xlabel('Die Count')
        ax.set_ylabel('Hardware Bin')

        # Save the plot to an in-memory buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        self.figures_list.append(buf)


        # 2D die_count to SW Bin visualization
        SWB_die_count = self.die_data_df['SoftwareBin'].value_counts()
        ax = SWB_die_count.plot(kind='barh')
        ax.set_xlabel('Die Count')
        ax.set_ylabel('Software Bin')

        # Save the plot to an in-memory buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        self.figures_list.append(buf)

    def load_vis_data(self, table_name):
            """
            This function loads data after prediction to the database.
            
            Ards: table_name
            """
            # Drop some columns before inserting into the database
            self.die_data_df.drop(['edge', 'bad_neighbor'], axis=1, inplace=True)

            # Insert DataFrame into SQL table
            self.die_data_df.to_sql(table_name, self.conn, if_exists='replace', index=False)
        

def main(db_name, mid, kernel='rbf', gamma='scale', nu=0.06):
    
    anomaly_detector = die_level_prediction(db_name, mid, kernel= kernel, gamma= gamma, nu= nu)

    # Load data from the database
    anomaly_detector.load_data_from_db()
    
    # Calculate local yield for each die
    anomaly_detector.calculate_local_yield_8()

    # Train the OCSVM model
    anomaly_detector.train_ocsvm()

    # Make predictions
    predictions, outliers = anomaly_detector.predict()
    
    # Create statistical plots
    anomaly_detector.visualize()
    
    # Load visual data
    anomaly_detector.load_vis_data('temporary_data')
    
    return anomaly_detector.num_outliers , anomaly_detector.count_df, anomaly_detector.figures_list

if __name__ == "__main__":
    db_name = 'database.db'
    mid = 4
    outliers_num, count_df, figure_list = main(db_name, mid)
    print('Number of outliers: {0}   Count DataFrame: {1}   List of Figures: {2}'.format(outliers_num, count_df, figure_list))