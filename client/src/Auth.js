import React from 'react';
import { Typography } from '@mui/material';

class Auth extends React.Component {

    constructor(props) {
        super(props);

        this.state = {};
    };

    // begin authentication
    componentDidMount() {
        
        // access token is passed in the anchor field for some reason
        let queryString = window.location.hash.replace(/^#/, '?')
        let urlParams = new URLSearchParams(queryString)

        // if token is present - resolve username
        if (urlParams.has('access_token')) {
            
            let xhr_request = new XMLHttpRequest()
            xhr_request.open("GET", "/username")

            // set token header
            xhr_request.setRequestHeader("Token", urlParams.get('access_token'))

            // API response callback
            xhr_request.onreadystatechange = function() {

                if (xhr_request.readyState === XMLHttpRequest.DONE) {

                    // finish authentication if username is valid
                    if (xhr_request.status === 200) {

                        // push root state without query params in order to hide them
                        window.history.replaceState({}, null, "/")

                        this.props.finishAuthentication(urlParams.get('access_token'), xhr_request.responseText)

                    // redirect to OAuth if username is invalid
                    } else {
                    
                        this.redirect()
    
                    }

                }

            }.bind(this)

            xhr_request.send()
        }

        // redirect to authentication screen if access token is not present/valid
        else {
            this.redirect()
        }
    }

    redirect() {
        let redirectUrl = window.ENV.OAUTH_ENDPOINT + '?'

        // parameters passed to OpenShift OAuth server
        let redirectParams = new URLSearchParams({
            client_id: window.ENV.OAUTH_CLIENT_ID,
            redirect_uri: window.location.origin,
            response_type: 'token',
            scope: 'user:info'
        })

        // redirect to OAuth server
        window.location.replace(redirectUrl + redirectParams.toString())
    }

    render() {

        return (
            <div style={{ textAlign: "center" }}>
                <Typography variant="subtitle2" color='textSecondary'>
                    Authenticating...
                </Typography>
            </div>
        )
    }

}

export default Auth;