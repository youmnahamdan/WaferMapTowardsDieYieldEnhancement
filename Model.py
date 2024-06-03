import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from math import sqrt, pow
import numpy as np
import io 
import matplotlib.pyplot as plt # for data visualization
import matplotlib
matplotlib.use('Agg') # To use Agg backend to prevent GUI creation in 

class die_level_prediction:
    def __init__(self, db_connection_string, mid, kernel='rbf', gamma='scale', nu=0.06, pool_size=5, max_overflow=10):
        self.kernel = kernel
        self.gamma = gamma
        self.nu = nu
        self.mid = mid
        self.db_connection_string = db_connection_string
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.die_data_df = None
        self.scaled_data_df = None
        self.model = None
        self.engine = None
        self.Session = None
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
        self.engine = create_engine(
            self.db_connection_string,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow
        )
        self.Session = sessionmaker(bind=self.engine)

    def load_data_from_db(self):
        """
        Load data from the database using the provided query.
        """
        if not self.engine:
            raise ValueError("Database engine not initialized. Call connect_to_db first.")
        
        with self.engine.connect() as connection:
            self.die_data_df = pd.read_sql('SELECT * FROM die_info WHERE MasterID = ?', connection, params=(self.mid,))
            result = connection.execute(text('SELECT CenterX, CenterY FROM wafer_config WHERE MasterID = :mid'), {'mid': self.mid})
            self.centers = result.fetchall()[0]
            result = connection.execute(text('SELECT DieWidth, DieHeight FROM wafer_config WHERE MasterID = :mid'), {'mid': self.mid})
            self.die_dim = result.fetchall()[0]
        
        # Storing count values
        self.count_df['MasterID'] = self.mid
        self.count_df['die_count'] = self.die_data_df['Passing'].count()
        self.count_df['bad_die_count_before']  = self.die_data_df['Passing'].value_counts()[0]
        self.count_df['good_die_count_before'] = self.die_data_df['Passing'].value_counts()[1]

    def calculate_effect_probability(self):
        """
        Calculate the effect probability weights for neighboring dies based on their
        distance from a reference die.

        Returns:
            List[float]: Weights for the corner, south-north, and left-right neighbors.
        """
        try:
            # Dimensions of the die
            x, y = self.die_dim
            
            # Ensure dimensions are non-zero to avoid division by zero
            if x <= 0 or y <= 0:
                raise ValueError("Die dimensions must be positive non-zero values.")
            
            # Calculate the total distance for normalization
            distance_corner = 4 / sqrt(pow(x, 2) + pow(y, 2))
            distance_lr = 2 / x
            distance_sn = 2 / y
            total_distance = distance_corner + distance_lr + distance_sn

            # Calculate weights for each neighbor type
            weight_corner = distance_corner / total_distance
            weight_lr = distance_lr / total_distance
            weight_sn = distance_sn / total_distance
            
            # Return weights in a specific order
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
        self.die_data_df['Visited'] = False     
        self.die_data_df['distance_from_center'] = 0.0
        self.die_data_df['edge'] = False
        self.die_data_df['local_yield'] = 0.0
        self.die_data_df['good_neighbor'] = 0
        self.die_data_df['bad_neighbor'] = 0
        ith_neighborhood = 8
        die_neighborhood = [(-1, 1), (0, 1), (1, 1), (-1, 0), (1, 0), (-1, -1), (0, -1), (1, -1)]
        effect_probability = self.calculate_effect_probability()

        for index, record in self.die_data_df.iterrows():
            if not record['Visited']:
                local_yield = 0
                good_neighbors = 0
                bad_neighbors = 0 ############3
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
                        else: ########
                            bad_neighbors +=1########3
                
                # Update dataframe with calculated values
                self.die_data_df.at[index, 'Visited'] = True
                self.die_data_df.at[index, 'good_neighbor'] = good_neighbors
                self.die_data_df.at[index, 'distance_from_center'] = sqrt(
                    pow(die_coords[0] - self.centers[0], 2) + pow(die_coords[1] - self.centers[1], 2)
                )
                self.die_data_df.at[index, 'local_yield'] = local_yield
                self.die_data_df.at[index, 'edge'] = (neighbors < 8)
                self.die_data_df.at[index, 'bad_neighbor'] = bad_neighbors

        # Calculate bad neighbors
        #self.die_data_df['bad_neighbor'] = ith_neighborhood - self.die_data_df['good_neighbor']

    def train_ocsvm(self):

        # Extract the features to train the model     
        self.features = self.die_data_df.loc[(self.die_data_df['edge'] == False) & (self.die_data_df.bad_neighbor.between(2,8)),['bad_neighbor','local_yield']]
        
        # Initialize and train the One-Class SVM model
        self.model = OneClassSVM(kernel = self.kernel, gamma = self.gamma, nu = self.nu )
        self.model.fit(self.features)

    def predict(self):
        """
        Predict anomalies using the trained One-Class SVM model.
        """
        if self.model is None:
            raise ValueError("Model must be trained before making predictions.")

        # Predict using the trained model
        predictions = self.model.predict(self.features)
        
        outliers_index = np.where(predictions == -1)[0]
        outliers = self.features.iloc[outliers_index]
        self.num_outliers = len(outliers)
        # Mark outliers as faulty
        self.die_data_df.loc[self.features.iloc[outliers_index].index, 'Passing'] = 0
        
        count_pass = self.die_data_df['Passing'].value_counts()
        self.count_df['bad_die_count_after']  = count_pass[0]
        self.count_df['good_die_count_after'] = count_pass[1]
        
        return predictions, outliers
    
    def visualize(self):
        # 2D die_count to propability visualization
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
        
        print(self.figures_list)

    def load_vis_data(self, table_name):
        """
        This function loads data after prediction to the database.
        """
        if not self.engine:
            raise ValueError("Database engine not initialized.")
        
        with self.engine.connect() as connection:
            self.die_data_df.drop(['edge', 'bad_neighbor'], axis=1, inplace=True)

            # Insert DataFrame into SQL table
            self.die_data_df.to_sql(table_name, connection, if_exists='replace', index=False)
        

def main(db_connection_string, mid, kernel='rbf', gamma='scale', nu=0.06):#, pool_size=5, max_overflow=10):
    
    anomaly_detector = die_level_prediction(db_connection_string, mid, kernel= kernel, gamma= gamma, nu= nu)#, pool_size=pool_size, max_overflow=max_overflow)

    # Load data from the database
    anomaly_detector.load_data_from_db()
    anomaly_detector.calculate_local_yield_8()

    # Train the OCSVM model
    anomaly_detector.train_ocsvm()

    # Make predictions
    predictions, outliers = anomaly_detector.predict()
    anomaly_detector.visualize()
    # Load visual data
    anomaly_detector.load_vis_data('temporary_data')
    
    anomaly_detector.Session.close_all()
    return anomaly_detector.num_outliers , anomaly_detector.count_df, anomaly_detector.figures_list

if __name__ == "__main__":
    db_connection_string = 'sqlite:///C:/Users/hp/OneDrive/Desktop/WaferMap/WaferMap/database.db'
    mid = 4
    print(main(db_connection_string, mid))